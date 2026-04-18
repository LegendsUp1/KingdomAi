#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Celo adapter connection methods implementation.
Will be merged with the main adapter file.
"""

@strict_blockchain_operation
def connect(self, private_key: str = None) -> bool:
    """Connect to Celo network and initialize Kit.
    
    Args:
        private_key: Optional private key for account connection
        
    Returns:
        bool: True if connection is successful
        
    Raises:
        BlockchainConnectionError: If connection fails
    """
    try:
        # Initialize Kit with web3 provider
        self.kit = Kit(self.rpc_url)
        self.web3 = self.kit.web3
        
        # Add POA middleware for Celo compatibility
        self.web3.middleware_onion.inject(native_geth_poa_middleware, layer=0)
        
        # Check network connectivity
        block_number = self.web3.eth.block_number
        logger.debug(f"Connected to {self.network_name}, current block: {block_number}")
        
        # Initialize account if private key is provided
        if private_key:
            self.set_account(private_key)
        
        self.is_connected = True
        return True
        
    except Exception as e:
        self.is_connected = False
        error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e

@strict_blockchain_operation
def disconnect(self) -> bool:
    """Disconnect from Celo network.
    
    Returns:
        bool: True if disconnect is successful
    """
    try:
        # Clear connection
        self.kit = None
        self.web3 = None
        self.is_connected = False
        
        logger.debug(f"Disconnected from {self.network_name}")
        return True
        
    except Exception as e:
        error_msg = f"Error during disconnect: {str(e)}"
        logger.error(error_msg)
        return False

@strict_blockchain_operation
def get_network_status(self) -> Dict:
    """Get current status of the network.
    
    Returns:
        Dict: Network status information
        
    Raises:
        BlockchainConnectionError: If connection fails
    """
    self._verify_connection()
    
    try:
        # Get basic network info
        block_number = self.web3.eth.block_number
        gas_price = self.web3.eth.gas_price
        
        # Get latest block details
        latest_block = self.web3.eth.get_block('latest')
        block_timestamp = latest_block.timestamp
        current_time = int(time.time())
        block_delay = current_time - block_timestamp
        
        # Get chain ID
        chain_id = self.web3.eth.chain_id
        
        # Create status report
        status = {
            'connected': self.is_connected,
            'network': self.network_name,
            'chain_id': chain_id,
            'block_number': block_number,
            'block_timestamp': block_timestamp,
            'block_delay': block_delay,
            'gas_price': str(gas_price),
            'gas_price_gwei': self.web3.from_wei(gas_price, 'gwei'),
            'sync_status': 'synced',  # Assume synced for RPC connections
            'rpc_url': self.rpc_url
        }
        
        # Get sync status if node is syncing
        try:
            sync_status = self.web3.eth.syncing
            if sync_status:
                status['sync_status'] = 'syncing'
                status['sync_progress'] = {
                    'current_block': sync_status.currentBlock,
                    'highest_block': sync_status.highestBlock,
                    'starting_block': sync_status.startingBlock,
                    'progress': (sync_status.currentBlock - sync_status.startingBlock) / 
                                (sync_status.highestBlock - sync_status.startingBlock)
                }
        except Exception:
            # Ignore errors for sync status
            pass
            
        # Get any Celo specific data
        try:
            # Get gas token info if using alternative fee currency
            if self.fee_currency:
                token_contract = self.kit.base_wrapper.create_and_get_contract_by_name(
                    self.fee_currency
                )
                status['fee_currency'] = {
                    'name': self.fee_currency,
                    'address': token_contract.address
                }
        except Exception:
            # Ignore Celo-specific errors
            pass
            
        return status
        
    except Exception as e:
        error_msg = f"Failed to get network status: {str(e)}"
        logger.error(error_msg)
        raise BlockchainConnectionError(error_msg) from e

@strict_blockchain_operation
def set_account(self, private_key: str) -> bool:
    """Set active account from private key.
    
    Args:
        private_key: Private key string
        
    Returns:
        bool: True if successful
        
    Raises:
        ValidationError: If private key is invalid
        WalletError: If account setup fails
    """
    try:
        # Initialize account from private key
        if private_key.startswith('0x'):
            self.private_key = private_key
        else:
            self.private_key = f"0x{private_key}"
            
        # Create Celo account
        self.account = CeloAccount.privateKeyToAccount(self.private_key)
        self.address = self.account.address
        
        # Update Kit with account
        self.kit.wallet_add_account = self.private_key
        
        logger.debug(f"Account set for {self.network_name}: {self.address}")
        return True
        
    except Exception as e:
        self.account = None
        self.private_key = None
        self.address = None
        
        error_msg = f"Failed to set account: {str(e)}"
        logger.error(error_msg)
        raise WalletError(error_msg) from e

@strict_blockchain_operation
def create_account(self) -> Dict:
    """Create a new Celo account.
    
    Returns:
        Dict: New account information with private key
        
    Raises:
        WalletError: If account creation fails
    """
    try:
        # Create new account
        new_account = CeloAccount.create()
        
        # Format account information
        account_info = {
            'address': new_account.address,
            'private_key': new_account.privateKey.hex(),
            'public_key': new_account.publicKey.hex()
        }
        
        logger.debug(f"Created new Celo account: {account_info['address']}")
        return account_info
        
    except Exception as e:
        error_msg = f"Failed to create new account: {str(e)}"
        logger.error(error_msg)
        raise WalletError(error_msg) from e
        
@strict_blockchain_operation
def validate_address(self, address: str) -> bool:
    """Validate a Celo address.
    
    Args:
        address: Address to validate
        
    Returns:
        bool: True if address is valid
    """
    # Address validation
    try:
        # Validate using Web3's validation
        if not self.web3:
            self.web3 = Web3()
            
        if not self.web3.is_address(address):
            return False
            
        # Convert to checksum address
        checksum_address = to_checksum_address(address)
        return True
        
    except Exception:
        return False
        
@strict_blockchain_operation
def get_token_contract(self, token_id: str):
    """Get Celo token contract.
    
    Args:
        token_id: Token ID (address or symbol)
        
    Returns:
        Contract object for the token
        
    Raises:
        ValidationError: If token_id is invalid
    """
    self._verify_connection()
    
    # Check if we have this token in cache
    if token_id in self.token_contracts:
        return self.token_contracts[token_id]
        
    try:
        # Check if token_id is a known stable token symbol
        if token_id in self.stable_tokens:
            # Get contract by name
            contract = self.kit.base_wrapper.create_and_get_contract_by_name(token_id)
        elif token_id in self.CURRENCY and not self.CURRENCY[token_id]['is_native']:
            # Get stable token contract
            if token_id == 'cUSD':
                contract = self.kit.contracts.get_stable_token()
            elif token_id == 'cEUR':
                contract = self.kit.contracts.get_stable_token_euro()
            elif token_id == 'cREAL':
                contract = self.kit.contracts.get_stable_token_real()
            else:
                raise ValidationError(f"Unknown token symbol: {token_id}")
        else:
            # Assume token_id is an address
            if not self.validate_address(token_id):
                raise ValidationError(f"Invalid token address: {token_id}")
                
            # Create ERC20 contract
            contract = self.kit.contracts.create_erc20(token_id)
            
        # Cache contract
        self.token_contracts[token_id] = contract
        return contract
        
    except Exception as e:
        error_msg = f"Failed to get token contract: {str(e)}"
        logger.error(error_msg)
        raise ValidationError(error_msg) from e
