#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hyperliquid blockchain adapter implementation.
Native, no-fallback adapter for Hyperliquid network integration.
"""

import os
import json
import time
import hashlib
import hmac
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
import requests

# Import blockchain base components
from blockchain.base_adapter import BlockchainAdapter, strict_blockchain_operation
from blockchain.exceptions import (
    BlockchainConnectionError,
    TransactionError, 
    ValidationError,
    WalletError
)

# Import cryptographic libraries
from eth_account import Account
from eth_account.messages import encode_structured_data

# Import logging
import logging
logger = logging.getLogger(__name__)


class HyperliquidAdapter(BlockchainAdapter):
    """Native Hyperliquid blockchain adapter.
    
    Implements all required blockchain operations for Hyperliquid network
    with no fallback mechanisms.
    """
    
    # Network configurations
    NETWORKS = {
        'mainnet': {
            'name': 'Hyperliquid Mainnet',
            'api_base': 'https://api.hyperliquid.xyz',
            'exchange_api': 'https://api.hyperliquid.xyz/exchange',
            'info_api': 'https://api.hyperliquid.xyz/info',
            'ws_endpoint': 'wss://api.hyperliquid.xyz/ws',
            'explorer_url': 'https://app.hyperliquid.xyz/explorer',
        },
        'testnet': {
            'name': 'Hyperliquid Testnet',
            'api_base': 'https://api.testnet.hyperliquid.xyz',
            'exchange_api': 'https://api.testnet.hyperliquid.xyz/exchange',
            'info_api': 'https://api.testnet.hyperliquid.xyz/info',
            'ws_endpoint': 'wss://api.testnet.hyperliquid.xyz/ws',
            'explorer_url': 'https://app.testnet.hyperliquid.xyz/explorer',
        }
    }
    
    # Currency configuration
    CURRENCY = {
        'USDC': {
            'name': 'USD Coin',
            'symbol': 'USDC',
            'decimals': 6,
            'is_native': True
        },
        'HLP': {
            'name': 'Hyperliquid Protocol Token',
            'symbol': 'HLP',
            'decimals': 18
        }
    }
    
    # Order types
    ORDER_TYPES = ['Limit', 'Market', 'Stop', 'StopLimit']
    
    # Sides
    SIDES = ['Buy', 'Sell']
    
    def __init__(self, network: str = 'mainnet', config: Dict = None):
        """Initialize Hyperliquid adapter.
        
        Args:
            network: Network name ('mainnet' or 'testnet')
            config: Additional configuration parameters
            
        Raises:
            ValidationError: If network is invalid
        """
        if network not in self.NETWORKS:
            raise ValidationError(f"Invalid Hyperliquid network: {network}. "
                                 f"Supported networks: {', '.join(self.NETWORKS.keys())}")
            
        # Initialize basic properties
        self.network = network
        self.network_name = self.NETWORKS[network]['name']
        self.api_base = self.NETWORKS[network]['api_base']
        self.exchange_api = self.NETWORKS[network]['exchange_api']
        self.info_api = self.NETWORKS[network]['info_api']
        self.ws_endpoint = self.NETWORKS[network]['ws_endpoint']
        self.explorer_url = self.NETWORKS[network]['explorer_url']
        
        # Set connection state
        self.is_connected = False
        self.session = None
        
        # Private key and account
        self.private_key = None
        self.account = None
        self.wallet_address = None
        
        # Override config if provided
        if config:
            if 'api_base' in config:
                self.api_base = config['api_base']
                
            if 'private_key' in config:
                self.private_key = config.get('private_key')
                
        super().__init__(network_name=self.network_name)
        
    def __str__(self) -> str:
        """Return string representation."""
        connection_status = "Connected" if self.is_connected else "Disconnected"
        return f"HyperliquidAdapter({self.network_name}, {connection_status})"
    
    @property
    def explorer_tx_url(self) -> str:
        """Get transaction explorer URL template."""
        return f"{self.explorer_url}/tx/"
    
    @property
    def explorer_address_url(self) -> str:
        """Get address explorer URL template."""
        return f"{self.explorer_url}/address/"
    
    @strict_blockchain_operation
    def _verify_connection(self) -> bool:
        """Verify connection to Hyperliquid network.
        
        Returns:
            bool: True if connection is successful
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.session:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Check if API is accessible
            response = self.session.get(f"{self.info_api}/universe")
            response.raise_for_status()
            
            # If we get here, connection is successful
            return True
        except Exception as e:
            self.is_connected = False
            raise BlockchainConnectionError(f"Failed to verify connection: {str(e)}") from e
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Hyperliquid network.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            # Initialize HTTP session
            self.session = requests.Session()
            self.session.headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Kingdom-AI/1.0 Hyperliquid-Native-Adapter'
            })
            
            # Initialize account if private key is provided
            if self.private_key:
                if not self.private_key.startswith('0x'):
                    self.private_key = f"0x{self.private_key}"
                self.account = Account.from_key(self.private_key)
                self.wallet_address = self.account.address
            
            # Verify connection
            self._verify_connection()
            
            # Set connection status
            self.is_connected = True
            logger.info(f"Connected to {self.network_name}")
            
            return True
            
        except Exception as e:
            self.is_connected = False
            self.session = None
            self.account = None
            error_msg = f"Failed to connect to {self.network_name}: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def disconnect(self) -> bool:
        """Disconnect from Hyperliquid network.
        
        Returns:
            bool: True if disconnected successfully
        """
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
            
        self.session = None
        self.is_connected = False
        logger.info(f"Disconnected from {self.network_name}")
        return True
            
    def validate_address(self, address: str) -> bool:
        """Validate Ethereum address format (Hyperliquid uses Ethereum addresses).
        
        Args:
            address: Address to validate
            
        Returns:
            bool: True if address is valid
        """
        if not address:
            return False
            
        try:
            # Validate the address structure (starting with 0x and being 42 characters long)
            return address.startswith('0x') and len(address) == 42 and all(c in '0123456789abcdefABCDEF' for c in address[2:])
        except Exception as e:
            logger.debug(f"Address validation error: {str(e)}")
            return False
            
    def validate_private_key(self, private_key: str) -> bool:
        """Validate private key format.
        
        Args:
            private_key: Private key to validate
            
        Returns:
            bool: True if private key is valid
        """
        if not private_key:
            return False
            
        # Ensure 0x prefix
        if not private_key.startswith('0x'):
            private_key = f"0x{private_key}"
            
        try:
            # Try to create an account with it
            Account.from_key(private_key)
            return True
        except Exception as e:
            logger.debug(f"Invalid private key format: {str(e)}")
            return False
    
    def _sign_request(self, message: Dict) -> Dict:
        """Sign a request using EIP-712 structured data signing.
        
        Args:
            message: Message to sign
            
        Returns:
            Dict: Signed message with signature
            
        Raises:
            ValidationError: If account is not initialized
        """
        if not self.account:
            raise ValidationError("Account not initialized. Please set a private key.")
            
        # Create EIP-712 structured data
        eip712_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                ],
                "Message": [{"name": "content", "type": "string"}],
            },
            "domain": {
                "name": "Hyperliquid",
                "version": "1",
                "chainId": 1 if self.network == 'mainnet' else 2,
            },
            "primaryType": "Message",
            "message": {"content": json.dumps(message)},
        }
        
        # Sign the message
        signature = self.account.sign_typed_data(
            domain_data=eip712_data["domain"],
            message_types=eip712_data["types"],
            message_data=eip712_data["message"],
        )
        
        # Return signed message
        return {
            "signature": signature.signature.hex(),
            "message": message,
            "address": self.wallet_address
        }
    
    @strict_blockchain_operation
    def get_balance(self, address: str = None, token_id: str = None) -> Decimal:
        """Get USDC balance for address.
        
        Args:
            address: Address to query, defaults to connected wallet address
            token_id: Optional token ID (not used in Hyperliquid)
            
        Returns:
            Decimal: Balance in USDC
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected or not self.session:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        # Use connected wallet address if not provided
        if address is None:
            if not self.wallet_address:
                raise ValidationError("No address provided and no wallet connected")
            address = self.wallet_address
            
        if not self.validate_address(address):
            raise ValidationError(f"Invalid address format: {address}")
            
        try:
            # Hyperliquid only supports USDC balances
            if token_id and token_id.upper() != 'USDC':
                raise ValidationError(f"Unsupported token ID: {token_id}. Only USDC is supported.")
                
            # Get user state
            response = self.session.post(
                f"{self.info_api}/user",
                json={"type": "clearinghouse", "user": address}
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract USDC balance
            cash_balance = Decimal(data.get("cash", "0"))
            
            # Convert to USDC (6 decimals)
            balance = cash_balance / Decimal(10 ** 6)
            
            return balance
                
        except Exception as e:
            error_msg = f"Failed to get balance: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_markets(self) -> List[Dict]:
        """Get available markets from Hyperliquid.
        
        Returns:
            List[Dict]: List of available market data
            
        Raises:
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.session:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Fetch universe data (markets)
            response = self.session.get(f"{self.info_api}/universe")
            response.raise_for_status()
            data = response.json()
            
            return data.get("universe", [])
        except Exception as e:
            error_msg = f"Failed to get markets: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_market_data(self, asset: str) -> Dict:
        """Get market data for a specific asset.
        
        Args:
            asset: Asset symbol (e.g., 'BTC')
            
        Returns:
            Dict: Market data for the asset
            
        Raises:
            ValidationError: If asset is invalid
            BlockchainConnectionError: If connection fails
        """
        if not self.is_connected or not self.session:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        try:
            # Normalize asset symbol
            asset = asset.upper()
            
            # Get all markets
            markets = self.get_markets()
            
            # Find the requested market
            market_data = None
            for market in markets:
                if market.get("name") == asset:
                    market_data = market
                    break
                    
            if not market_data:
                raise ValidationError(f"Market not found for asset: {asset}")
                
            return market_data
        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            error_msg = f"Failed to get market data: {str(e)}"
            logger.error(error_msg)
            raise BlockchainConnectionError(error_msg) from e
            
    @strict_blockchain_operation
    def create_transaction(self, transaction: Dict, **kwargs) -> Dict:
        """Create a Hyperliquid transaction (order).
        
        Args:
            transaction: Transaction parameters
                - asset: Asset symbol (e.g., 'BTC')
                - side: 'Buy' or 'Sell'
                - type: Order type ('Limit', 'Market', 'Stop', 'StopLimit')
                - amount: Order amount
                - price: Limit price (for Limit and StopLimit orders)
                - stop_price: Stop price (for Stop and StopLimit orders)
            **kwargs: Additional parameters
            
        Returns:
            Dict: Transaction object ready for signing
            
        Raises:
            ValidationError: If transaction parameters are invalid
            TransactionError: If transaction creation fails
        """
        if not self.is_connected or not self.session:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not transaction:
            raise ValidationError("Transaction parameters required")
            
        try:
            # Validate and extract parameters
            asset = transaction.get('asset')
            if not asset:
                raise ValidationError("Asset symbol required")
                
            side = transaction.get('side')
            if not side or side not in self.SIDES:
                valid_sides = ", ".join(self.SIDES)
                raise ValidationError(f"Invalid side: {side}. Valid values: {valid_sides}")
                
            order_type = transaction.get('type')
            if not order_type or order_type not in self.ORDER_TYPES:
                valid_types = ", ".join(self.ORDER_TYPES)
                raise ValidationError(f"Invalid order type: {order_type}. Valid values: {valid_types}")
                
            amount = transaction.get('amount')
            if not amount or float(amount) <= 0:
                raise ValidationError("Invalid amount")
                
            # Price is required for Limit and StopLimit orders
            price = transaction.get('price')
            if order_type in ['Limit', 'StopLimit'] and (not price or float(price) <= 0):
                raise ValidationError(f"Price required for {order_type} orders")
                
            # Stop price is required for Stop and StopLimit orders
            stop_price = transaction.get('stop_price')
            if order_type in ['Stop', 'StopLimit'] and (not stop_price or float(stop_price) <= 0):
                raise ValidationError(f"Stop price required for {order_type} orders")
                
            # Get market data
            market_data = self.get_market_data(asset)
            
            # Calculate order size based on market specification
            # Hyperliquid uses standardized contracts
            szDecimals = int(market_data.get("szDecimals", 0))
            order_size = float(amount) * (10 ** szDecimals)
            
            # Create order payload
            order = {
                "coin": market_data.get("name"),
                "is_buy": side == 'Buy',
                "sz": str(order_size),
                "limit_px": str(price) if price else None,
                "reduce_only": False
            }
            
            # Add order type specific fields
            if order_type == 'Market':
                order["order_type"] = {"market": {}}
            elif order_type == 'Limit':
                order["order_type"] = {"limit": {"tif": "Gtc"}}
            elif order_type == 'Stop':
                order["order_type"] = {"trigger": {"trigger_px": str(stop_price), "is_market": True}}
            elif order_type == 'StopLimit':
                order["order_type"] = {"trigger": {"trigger_px": str(stop_price), "is_market": False}}
            
            # Create the transaction object
            tx_object = {
                'order': order,
                'asset': asset,
                'side': side,
                'type': order_type,
                'amount': amount,
                'price': price,
                'stop_price': stop_price,
                'market_data': market_data,
                'from_address': self.wallet_address,
                'signed': False,
                'timestamp': int(time.time() * 1000)
            }
            
            return tx_object
            
        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            error_msg = f"Failed to create transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Dict, private_key: str = None) -> Dict:
        """Sign a Hyperliquid transaction (order).
        
        Args:
            transaction: Transaction object from create_transaction
            private_key: Private key for signing (optional)
            
        Returns:
            Dict: Signed transaction ready for broadcasting
            
        Raises:
            ValidationError: If transaction is invalid
            TransactionError: If signing fails
            WalletError: If private key is invalid
        """
        if not self.is_connected:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not transaction or 'order' not in transaction:
            raise ValidationError("Invalid transaction object")
            
        try:
            # Determine the private key to use
            key = None
            if private_key:
                # Use provided private key
                if not self.validate_private_key(private_key):
                    raise WalletError("Invalid private key format")
                    
                if not private_key.startswith('0x'):
                    private_key = f"0x{private_key}"
                    
                key = private_key
                # Create temporary account
                temp_account = Account.from_key(key)
                wallet_address = temp_account.address
            elif self.private_key and self.account:
                # Use instance private key and account
                key = self.private_key
                wallet_address = self.wallet_address
            else:
                raise WalletError("No private key available for signing")
                
            # Create the order message
            order_msg = {
                "action": {
                    "order": {
                        "order": transaction['order']
                    }
                },
                "nonce": transaction['timestamp']
            }
            
            # Sign the order using EIP-712
            if private_key:
                # Use temporary account for signing
                eip712_data = {
                    "types": {
                        "EIP712Domain": [
                            {"name": "name", "type": "string"},
                            {"name": "version", "type": "string"},
                            {"name": "chainId", "type": "uint256"},
                        ],
                        "Message": [{"name": "content", "type": "string"}],
                    },
                    "domain": {
                        "name": "Hyperliquid",
                        "version": "1",
                        "chainId": 1 if self.network == 'mainnet' else 2,
                    },
                    "primaryType": "Message",
                    "message": {"content": json.dumps(order_msg)},
                }
                
                # Sign the message
                signature = temp_account.sign_typed_data(
                    domain_data=eip712_data["domain"],
                    message_types=eip712_data["types"],
                    message_data=eip712_data["message"],
                )
                
                signature_hex = signature.signature.hex()
            else:
                # Use instance method for signing
                signed_data = self._sign_request(order_msg)
                signature_hex = signed_data['signature']
                
            # Create signed transaction object
            signed_transaction = transaction.copy()
            signed_transaction['signed'] = True
            signed_transaction['signature'] = signature_hex
            signed_transaction['wallet_address'] = wallet_address
            
            # Create the final signed payload
            signed_transaction['payload'] = {
                "signature": signature_hex,
                "signer": wallet_address,
                "action": order_msg['action'],
                "nonce": order_msg['nonce']
            }
            
            return signed_transaction
            
        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            error_msg = f"Failed to sign transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Dict) -> Dict:
        """Broadcast a signed Hyperliquid transaction (order).
        
        Args:
            signed_transaction: Signed transaction from sign_transaction
            
        Returns:
            Dict: Transaction receipt with order ID and status
            
        Raises:
            ValidationError: If signed transaction is invalid
            TransactionError: If broadcasting fails
        """
        if not self.is_connected or not self.session:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        # Validate signed transaction
        if not signed_transaction or not signed_transaction.get('signed', False) or 'payload' not in signed_transaction:
            raise ValidationError("Transaction is not signed or invalid")
            
        try:
            # Get the signed payload
            payload = signed_transaction['payload']
            
            # Send the order to Hyperliquid API
            response = self.session.post(
                f"{self.exchange_api}/order",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # Check for errors in response
            if 'error' in result and result['error']:
                error_msg = f"Order failed: {result['error']}"
                logger.error(error_msg)
                raise TransactionError(error_msg)
                
            # Create receipt
            order_data = result.get('data', {})
            order_id = order_data.get('order_id', 'unknown')
            order_status = order_data.get('status', 'pending')
            
            receipt = {
                'txid': order_id,
                'hash': order_id,  # Hyperliquid uses order IDs instead of transaction hashes
                'confirmed': order_status == 'filled',
                'status': order_status,
                'explorer_url': f"{self.explorer_url}?user={signed_transaction['wallet_address']}",
                'asset': signed_transaction['asset'],
                'side': signed_transaction['side'],
                'type': signed_transaction['type'],
                'amount': signed_transaction['amount'],
                'price': signed_transaction.get('price'),
                'stop_price': signed_transaction.get('stop_price'),
                'wallet_address': signed_transaction['wallet_address'],
                'timestamp': signed_transaction['timestamp'],
                'raw_response': result
            }
            
            return receipt
            
        except requests.RequestException as e:
            error_msg = f"Failed to broadcast transaction: API error - {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to broadcast transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def get_transaction_status(self, tx_id: str, wallet_address: str = None) -> Dict:
        """Get status of a Hyperliquid transaction (order).
        
        Args:
            tx_id: Transaction/order ID
            wallet_address: Wallet address that placed the order
            
        Returns:
            Dict: Transaction/order status and details
            
        Raises:
            ValidationError: If tx_id or wallet_address is invalid
            TransactionError: If status check fails
        """
        if not self.is_connected or not self.session:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not tx_id:
            raise ValidationError("Invalid transaction/order ID")
            
        # Use connected wallet address if not provided
        if not wallet_address:
            if not self.wallet_address:
                raise ValidationError("No wallet address provided and no wallet connected")
            wallet_address = self.wallet_address
            
        if not self.validate_address(wallet_address):
            raise ValidationError(f"Invalid wallet address format: {wallet_address}")
            
        try:
            # Get user orders
            response = self.session.post(
                f"{self.info_api}/orders",
                json={"user": wallet_address, "nOrders": 100}
            )
            response.raise_for_status()
            orders = response.json().get('orders', [])
            
            # Find the specific order
            order_data = None
            for order in orders:
                if order.get('oid') == tx_id:
                    order_data = order
                    break
                    
            if not order_data:
                # Order not found, try to get it from fills
                response = self.session.post(
                    f"{self.info_api}/fills",
                    json={"user": wallet_address, "nFills": 100}
                )
                response.raise_for_status()
                fills = response.json().get('fills', [])
                
                # Look for fills with this order ID
                for fill in fills:
                    if fill.get('oid') == tx_id:
                        order_data = {
                            'oid': tx_id,
                            'status': 'filled',
                            'coin': fill.get('coin'),
                            'side': 'buy' if fill.get('is_buyer', False) else 'sell',
                            'sz': fill.get('sz'),
                            'px': fill.get('px'),
                            'type': 'market',
                            'timestamp': fill.get('time', 0)
                        }
                        break
                        
            # Determine status
            if order_data:
                # Order found
                status = order_data.get('status', 'pending').lower()
                coin = order_data.get('coin', '')
                side = 'Buy' if order_data.get('side', '') == 'buy' else 'Sell'
                size = order_data.get('sz', '0')
                price = order_data.get('px', '0')
                order_type = order_data.get('type', 'limit')
                timestamp = order_data.get('timestamp', 0)
                
                # Convert status
                if status == 'filled':
                    confirmed = True
                    status = 'success'
                elif status in ['canceled', 'rejected']:
                    confirmed = True
                    status = 'failed'
                else:
                    confirmed = False
                    status = 'pending'
                    
                return {
                    'txid': tx_id,
                    'hash': tx_id,
                    'confirmed': confirmed,
                    'status': status,
                    'explorer_url': f"{self.explorer_url}?user={wallet_address}",
                    'asset': coin,
                    'side': side,
                    'amount': size,
                    'price': price,
                    'type': order_type,
                    'timestamp': timestamp,
                    'wallet_address': wallet_address,
                    'raw_data': order_data
                }
            else:
                # Order not found
                return {
                    'txid': tx_id,
                    'hash': tx_id,
                    'confirmed': False,
                    'status': 'unknown',
                    'explorer_url': f"{self.explorer_url}?user={wallet_address}",
                    'wallet_address': wallet_address
                }
                
        except Exception as e:
            error_msg = f"Failed to get transaction status: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
            
    @strict_blockchain_operation
    def cancel_transaction(self, tx_id: str) -> bool:
        """Cancel a pending Hyperliquid order.
        
        Args:
            tx_id: Transaction/order ID to cancel
            
        Returns:
            bool: True if cancel was successful
            
        Raises:
            ValidationError: If tx_id is invalid
            TransactionError: If cancellation fails
        """
        if not self.is_connected or not self.session:
            raise BlockchainConnectionError(f"Not connected to {self.network_name}")
            
        if not tx_id:
            raise ValidationError("Invalid transaction/order ID")
            
        if not self.account or not self.wallet_address:
            raise WalletError("No wallet connected. Cannot cancel order.")
            
        try:
            # Create cancel message
            cancel_msg = {
                "action": {
                    "cancel": {
                        "oid": tx_id
                    }
                },
                "nonce": int(time.time() * 1000)
            }
            
            # Sign the message
            signed_data = self._sign_request(cancel_msg)
            
            # Create the cancel payload
            cancel_payload = {
                "signature": signed_data['signature'],
                "signer": self.wallet_address,
                "action": cancel_msg['action'],
                "nonce": cancel_msg['nonce']
            }
            
            # Send the cancel request
            response = self.session.post(
                f"{self.exchange_api}/cancel",
                json=cancel_payload
            )
            response.raise_for_status()
            result = response.json()
            
            # Check for errors in response
            if 'error' in result and result['error']:
                error_msg = f"Cancel failed: {result['error']}"
                logger.error(error_msg)
                raise TransactionError(error_msg)
                
            # Success
            return True
            
        except Exception as e:
            error_msg = f"Failed to cancel transaction: {str(e)}"
            logger.error(error_msg)
            raise TransactionError(error_msg) from e
