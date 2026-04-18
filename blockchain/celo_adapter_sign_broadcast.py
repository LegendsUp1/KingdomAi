#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Celo adapter transaction signing and broadcasting methods implementation.
Will be merged with the main adapter file.
"""

@strict_blockchain_operation
def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
    """Sign a Celo transaction.
    
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
    
    # Verify transaction contains required fields
    if 'tx_params' not in transaction:
        raise ValidationError("Invalid transaction: missing tx_params")
    
    # Get private key
    pk = private_key or self.private_key
    if not pk:
        raise WalletError("No private key available for signing")
        
    try:
        # Get transaction parameters
        tx_params = transaction['tx_params']
        
        # Build transaction
        # Celo transactions can include feeCurrency, so we need to use the right transaction type
        if 'feeCurrency' in tx_params:
            # Create Celo custom transaction
            signed_tx = self.web3.eth.account.sign_transaction(
                tx_params, 
                private_key=pk
            )
        else:
            # Standard Ethereum-style transaction
            signed_tx = self.web3.eth.account.sign_transaction(
                tx_params, 
                private_key=pk
            )
            
        # Create the response
        signed_data = transaction.copy()
        signed_data.update({
            'signed': True,
            'status': 'signed',
            'raw_tx': signed_tx.rawTransaction.hex(),
            'tx_hash': signed_tx.hash.hex(),
            'signature': {
                'r': hex(signed_tx.r),
                's': hex(signed_tx.s),
                'v': signed_tx.v
            }
        })
        
        logger.debug(f"Transaction signed: {signed_data['tx_hash']}")
        return signed_data
        
    except Exception as e:
        error_msg = f"Failed to sign transaction: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e

@strict_blockchain_operation
def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
    """Broadcast a signed Celo transaction.
    
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
    if 'raw_tx' not in signed_transaction:
        raise ValidationError("Invalid signed transaction: missing 'raw_tx' field")
    
    try:
        # Get the raw transaction
        raw_tx = signed_transaction['raw_tx']
        
        # Convert to bytes if it's a hex string
        if isinstance(raw_tx, str):
            if raw_tx.startswith('0x'):
                raw_tx = bytes.fromhex(raw_tx[2:])
            else:
                raw_tx = bytes.fromhex(raw_tx)
                
        # Send the transaction
        tx_hash = self.web3.eth.send_raw_transaction(raw_tx)
        tx_hash_hex = tx_hash.hex()
        
        # Create response with transaction details
        response = {
            'txid': tx_hash_hex,
            'hash': tx_hash_hex,
            'status': 'pending',
            'confirmed': False,
            'sender': signed_transaction['sender'],
            'recipient': signed_transaction['recipient'],
            'amount': signed_transaction['amount'],
            'explorer_url': self.explorer_tx_url().format(txid=tx_hash_hex),
            'type': signed_transaction['type']
        }
        
        # Add token info if it's a token transfer
        if 'token_id' in signed_transaction:
            response['token_id'] = signed_transaction['token_id']
            response['token_address'] = signed_transaction['token_address']
            
        # Add fee currency info if present
        if 'fee_currency' in signed_transaction:
            response['fee_currency'] = signed_transaction['fee_currency']
            response['fee_currency_address'] = signed_transaction['fee_currency_address']
            
        logger.info(f"Transaction broadcast: {response['txid']} ({response['type']})")
        return response
        
    except Exception as e:
        error_msg = f"Failed to broadcast transaction: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e

@strict_blockchain_operation
def get_transaction_status(self, tx_id: str) -> Dict:
    """Get the status of a Celo transaction.
    
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
        # Convert transaction hash to bytes if it's a hex string
        if isinstance(tx_id, str):
            if tx_id.startswith('0x'):
                tx_hash = tx_id
            else:
                tx_hash = f"0x{tx_id}"
        else:
            tx_hash = tx_id
            
        # Initialize status
        status = {
            'txid': tx_hash,
            'hash': tx_hash,
            'status': 'unknown',
            'confirmed': False,
            'explorer_url': self.explorer_tx_url().format(txid=tx_hash)
        }
        
        # Check if the transaction is in the mempool
        try:
            # Get transaction from mempool
            tx = self.web3.eth.get_transaction(tx_hash)
            
            if tx:
                # Transaction found in mempool
                status['status'] = 'pending'
                status['block_hash'] = tx.get('blockHash', None)
                status['block_number'] = tx.get('blockNumber', None)
                status['from'] = tx['from']
                status['to'] = tx['to']
                status['value'] = str(tx['value'])
                status['nonce'] = tx['nonce']
                status['gas'] = tx['gas']
                status['gas_price'] = str(tx['gasPrice'])
                
                # Add Celo-specific fields
                if 'feeCurrency' in tx:
                    status['fee_currency'] = tx['feeCurrency']
                    
                # Check if transaction has been mined
                if tx.get('blockNumber') is not None:
                    status['status'] = 'confirmed'
                    status['confirmed'] = True
                    
                    # Try to get the receipt to check success/failure
                    try:
                        receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                        if receipt:
                            status['receipt'] = {
                                'block_hash': receipt['blockHash'].hex(),
                                'block_number': receipt['blockNumber'],
                                'gas_used': receipt['gasUsed'],
                                'cumulative_gas_used': receipt['cumulativeGasUsed'],
                                'status': receipt['status']
                            }
                            
                            # Update status based on receipt
                            if receipt['status'] == 1:
                                status['status'] = 'success'
                            else:
                                status['status'] = 'failed'
                                
                            # Add logs count
                            if 'logs' in receipt:
                                status['receipt']['logs_count'] = len(receipt['logs'])
                    except Exception as e:
                        logger.debug(f"Error getting receipt: {str(e)}")
                        
        except Exception as e:
            # Transaction not found in mempool
            logger.debug(f"Transaction not in mempool: {str(e)}")
            
            # Try to get the receipt directly (might be already mined)
            try:
                receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    status['status'] = 'success' if receipt['status'] == 1 else 'failed'
                    status['confirmed'] = True
                    status['receipt'] = {
                        'block_hash': receipt['blockHash'].hex(),
                        'block_number': receipt['blockNumber'],
                        'gas_used': receipt['gasUsed'],
                        'cumulative_gas_used': receipt['cumulativeGasUsed'],
                        'status': receipt['status']
                    }
                    
                    # Add logs count
                    if 'logs' in receipt:
                        status['receipt']['logs_count'] = len(receipt['logs'])
                        
                    # Add from/to addresses
                    status['from'] = receipt['from']
                    status['to'] = receipt['to']
            except Exception as e2:
                # Transaction not found at all
                logger.debug(f"Transaction receipt not found: {str(e2)}")
                
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
    """Estimate fees for a Celo transaction.
    
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
        gas_price = self.web3.eth.gas_price
        
        # Define fee speeds
        speeds = {
            'slow': 0.9,  # 90% of current gas price
            'average': 1.0,  # 100% of current gas price
            'fast': 1.2  # 120% of current gas price
        }
        
        # Calculate fees for each speed
        fees = {
            speed: int(gas_price * multiplier)
            for speed, multiplier in speeds.items()
        }
        
        # If a transaction is provided, estimate its gas usage
        gas_limit = 21000  # Default gas limit for simple transfers
        if transaction:
            if 'tx_params' in transaction:
                # Use the transaction parameters to estimate gas
                tx_params = transaction['tx_params'].copy()
                
                # Remove nonce and gasPrice if present
                if 'nonce' in tx_params:
                    del tx_params['nonce']
                if 'gasPrice' in tx_params:
                    del tx_params['gasPrice']
                    
                # Estimate gas
                try:
                    gas_limit = self.web3.eth.estimate_gas(tx_params)
                except Exception as e:
                    logger.debug(f"Error estimating gas: {str(e)}")
                    
                    # Use the gas_limit from transaction if available
                    if 'gas_limit' in transaction:
                        gas_limit = transaction['gas_limit']
                    elif 'gas' in tx_params:
                        gas_limit = tx_params['gas']
            
            # For token transfers, use higher default gas
            if transaction.get('type') == 'token_transfer':
                if gas_limit == 21000:  # If still using the default
                    gas_limit = 65000  # Higher default for token transfers
        
        # Calculate total fees for different speeds
        total_fees = {}
        for speed, price in fees.items():
            # Calculate total fee in wei
            total_fee_wei = price * gas_limit
            
            # Convert to CELO
            total_fee_celo = Decimal(total_fee_wei) / Decimal(10**18)
            
            # Add to results
            total_fees[speed] = total_fee_celo
        
        # Create the response
        result = {
            'gas_price': str(gas_price),
            'gas_price_gwei': self.web3.from_wei(gas_price, 'gwei'),
            'gas_limit': gas_limit,
            'slow': total_fees['slow'],
            'average': total_fees['average'],
            'fast': total_fees['fast'],
            'unit': 'CELO'
        }
        
        # Add price in USD using cUSD if available
        try:
            if 'cUSD' in self.stable_tokens:
                # Get exchange rate
                exchange_rate = self.kit.contracts.exchange.get_exchange_rate('CELO', 'cUSD')
                
                # Calculate USD values
                result['slow_usd'] = total_fees['slow'] * Decimal(exchange_rate)
                result['average_usd'] = total_fees['average'] * Decimal(exchange_rate)
                result['fast_usd'] = total_fees['fast'] * Decimal(exchange_rate)
                result['exchange_rate_usd'] = Decimal(exchange_rate)
        except Exception as e:
            logger.debug(f"Error getting USD values: {str(e)}")
            
        # Handle fee currencies
        if transaction and 'fee_currency' in transaction:
            fee_currency = transaction['fee_currency']
            result['fee_currency'] = fee_currency
            
            # If using stable token for fees, update fee estimates
            try:
                # Get stable token fee multiplier (if different from CELO)
                exchange_rate = Decimal(1.0)  # Default to 1:1
                
                if fee_currency != 'CELO':
                    # Get exchange rate
                    exchange_rate = self.kit.contracts.exchange.get_exchange_rate('CELO', fee_currency)
                    
                    # Apply exchange rate to fee estimates
                    result[f'slow_{fee_currency.lower()}'] = total_fees['slow'] * exchange_rate
                    result[f'average_{fee_currency.lower()}'] = total_fees['average'] * exchange_rate
                    result[f'fast_{fee_currency.lower()}'] = total_fees['fast'] * exchange_rate
                    result['exchange_rate'] = float(exchange_rate)
                    result['unit'] = fee_currency
            except Exception as e:
                logger.debug(f"Error calculating fees in {fee_currency}: {str(e)}")
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to estimate fee: {str(e)}"
        logger.error(error_msg)
        raise TransactionError(error_msg) from e
