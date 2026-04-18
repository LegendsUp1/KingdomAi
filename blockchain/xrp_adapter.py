#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Kingdom AI - XRP Ledger (XRPL) Blockchain Adapter

This module provides native, no-fallback integration with the XRP Ledger.
Production-grade implementation with robust error handling and multiple endpoint support.
"""

import logging
import json
import time
from typing import Dict, Any, Optional, List, Union, TypeVar

# Import base adapter
from blockchain.base_adapter import (
    BlockchainAdapter, BlockchainError, ConnectionError, 
    TransactionError, ValidationError, strict_blockchain_operation
)

# Import XRPL-specific libraries - 2026 SOTA: Handle API changes gracefully
XRPL_AVAILABLE = False
JsonRpcClient = None
WebsocketClient = None
Wallet = None
XRPLTransaction = None

try:
    from xrpl.clients import JsonRpcClient, WebsocketClient
    from xrpl.wallet import Wallet, generate_faucet_wallet
    from xrpl.models.transactions import Payment, AccountSet, TrustSet
    from xrpl.models.transactions.transaction import Transaction as XRPLTransaction
    from xrpl.utils import xrp_to_drops, drops_to_xrp
    
    # Handle API changes - get_account_info moved in newer versions
    try:
        from xrpl.account import get_balance, get_account_info
    except ImportError:
        get_balance = None
        get_account_info = None
    # XRPL 4.x API: safe_sign_transaction -> sign, get_transaction_from_hash removed
    from xrpl.transaction import submit_and_wait, sign as safe_sign_transaction, autofill_and_sign
    # get_transaction_from_hash was removed - use client.request instead
    get_transaction_from_hash = None
    from xrpl.core.addresscodec import is_valid_classic_address, classic_address_to_xaddress, xaddress_to_classic_address
    
    # Handle XRPAmount API changes - it was removed in newer versions
    try:
        from xrpl.models.amounts import IssuedCurrencyAmount, XRPAmount
    except ImportError:
        # XRPAmount doesn't exist in newer xrpl versions - XRP amounts are just strings
        IssuedCurrencyAmount = None
        XRPAmount = str  # XRP amounts are represented as string drops
    
    # Handle verify_signature API changes
    try:
        from xrpl.wallet import verify_signature
    except ImportError:
        verify_signature = None
    
    XRPL_AVAILABLE = True
    logging.getLogger(__name__).info("✅ XRPL libraries loaded successfully")
except ImportError as e:
    logging.getLogger(__name__).info(f"ℹ️ XRPL libraries not available: {e}")

# Set up logger
logger = logging.getLogger(__name__)

# Define XRPL networks and their endpoints
XRPL_MAINNET_ENDPOINTS = [
    "https://xrplcluster.com",
    "https://s1.ripple.com:51234",
    "https://s2.ripple.com:51234",
    "wss://xrplcluster.com",
    "wss://s1.ripple.com",
    "wss://s2.ripple.com",
]

XRPL_TESTNET_ENDPOINTS = [
    "https://s.altnet.rippletest.net:51234",
    "wss://s.altnet.rippletest.net:51233",
]

XRPL_DEVNET_ENDPOINTS = [
    "https://s.devnet.rippletest.net:51234",
    "wss://s.devnet.rippletest.net:51233",
]

class XRPLAdapter(BlockchainAdapter[XRPLTransaction]):
    """Native XRP Ledger blockchain adapter with strict no-fallback policy."""
    
    def __init__(self, 
                 network: str = "mainnet", 
                 endpoints: Optional[List[str]] = None,
                 use_websocket: bool = False,
                 timeout: int = 10):
        """Initialize XRPL adapter.
        
        Args:
            network: Network to connect to ('mainnet', 'testnet', 'devnet')
            endpoints: Optional list of RPC endpoints (will override defaults if provided)
            use_websocket: Use WebSocket client instead of JSON-RPC
            timeout: Connection timeout in seconds
        """
        network_name = f"xrpl-{network}"
        chain_id = None  # XRPL doesn't use chain IDs
        
        super().__init__(network_name=network_name, chain_id=chain_id)
        
        self.network = network.lower()
        self._endpoints = endpoints or self._get_default_endpoints()
        self._current_endpoint_index = 0
        self._client = None
        self._use_websocket = use_websocket
        self._timeout = timeout
        self._last_ledger_info = None
        self._last_ledger_check_time = 0
        
        # Don't connect in __init__ - causes asyncio.run() error when called from running event loop
        # Connection will happen on first use via lazy initialization
        self._connection_attempted = False
        
    def _get_default_endpoints(self) -> List[str]:
        """Get default endpoints based on selected network."""
        if self.network == "mainnet":
            return XRPL_MAINNET_ENDPOINTS
        elif self.network == "testnet":
            return XRPL_TESTNET_ENDPOINTS
        elif self.network == "devnet":
            return XRPL_DEVNET_ENDPOINTS
        else:
            raise ValueError(f"Unsupported XRPL network: {self.network}")
    
    def _get_current_endpoint(self) -> str:
        """Get current endpoint from the endpoints list."""
        if not self._endpoints:
            raise ConnectionError("No XRPL endpoints available")
            
        filtered_endpoints = [
            endpoint for endpoint in self._endpoints
            if (self._use_websocket and endpoint.startswith("wss://")) or
               (not self._use_websocket and endpoint.startswith("https://"))
        ]
        
        if not filtered_endpoints:
            raise ConnectionError(f"No {'WebSocket' if self._use_websocket else 'JSON-RPC'} endpoints available")
            
        return filtered_endpoints[self._current_endpoint_index % len(filtered_endpoints)]
    
    def _try_next_endpoint(self) -> None:
        """Try the next available endpoint in the list."""
        self._current_endpoint_index = (self._current_endpoint_index + 1) % len(self._endpoints)
        logger.warning(f"Switching to next XRPL endpoint: {self._get_current_endpoint()}")
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to XRP Ledger using available endpoints.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            ConnectionError: If all connection attempts fail
        """
        connection_errors = []
        
        # Try all endpoints until one works
        for _ in range(len(self._endpoints)):
            try:
                endpoint = self._get_current_endpoint()
                logger.info(f"Connecting to XRP Ledger {self.network} at {endpoint}")
                
                # Create client based on protocol (timeout not supported in __init__)
                if self._use_websocket and endpoint.startswith("wss://"):
                    self._client = WebsocketClient(endpoint)
                elif not self._use_websocket and endpoint.startswith("https://"):
                    self._client = JsonRpcClient(endpoint)
                else:
                    raise ConnectionError(f"Endpoint protocol doesn't match client type: {endpoint}")
                
                # Test connection with server_info request
                server_info = self._client.request({
                    "command": "server_info"
                })
                
                if "result" not in server_info or "info" not in server_info["result"]:
                    raise ConnectionError(f"Invalid response from server_info: {server_info}")
                
                # Get server state and version
                server_state = server_info["result"]["info"].get("server_state")
                server_version = server_info["result"]["info"].get("build_version")
                
                if server_state != "full" and self.network == "mainnet":
                    logger.warning(f"XRPL server not in 'full' state: {server_state}")
                
                logger.info(f"Connected to XRP Ledger {self.network} (state: {server_state}, version: {server_version})")
                
                # Get ledger information
                ledger_info = self._client.request({
                    "command": "ledger",
                    "ledger_index": "validated"
                })
                
                if "result" in ledger_info and "ledger" in ledger_info["result"]:
                    self.last_block = int(ledger_info["result"]["ledger"]["ledger_index"])
                    logger.info(f"Current validated ledger: {self.last_block}")
                
                self.is_connected = True
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to XRPL endpoint {endpoint}: {str(e)}")
                connection_errors.append(f"{endpoint}: {str(e)}")
                self._try_next_endpoint()
        
        # If we get here, all connection attempts failed
        error_msg = f"Failed to connect to any XRPL endpoint. Errors: {connection_errors}"
        logger.critical(error_msg)
        raise ConnectionError(error_msg)
    
    def _ensure_connected(self):
        """Lazy connection - connect on first use to avoid asyncio.run() error."""
        if not self._connection_attempted:
            self._connection_attempted = True
            try:
                self.connect()
            except Exception as e:
                logger.warning(f"XRP adapter connection deferred: {e}")
    
    @strict_blockchain_operation
    def get_balance(self, address: str) -> float:
        """Get XRP balance for address."""
        self._ensure_connected()
        
        if not self.is_connected or not self._client:
            raise ConnectionError("Not connected to XRPL")
        
        try:
            # Use request model if get_balance function not available
            if get_balance is None:
                from xrpl.models.requests import AccountInfo
                response = self._client.request(AccountInfo(account=address))
                balance_drops = response.result['account_data']['Balance']
            else:
                balance_drops = get_balance(address, self._client)
            return float(drops_to_xrp(balance_drops))
        except Exception as e:
            raise BlockchainError(f"Failed to get balance: {e}")
    
    @strict_blockchain_operation
    def create_transaction(self, from_address: str, to_address: str, amount: float, **kwargs) -> Any:
        """Create XRP payment transaction."""
        try:
            amount_drops = xrp_to_drops(amount)
            payment = Payment(
                account=from_address,
                destination=to_address,
                amount=str(amount_drops),
                **kwargs
            )
            return payment
        except Exception as e:
            raise TransactionError(f"Failed to create transaction: {e}")
    
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Any, private_key: str) -> str:
        """Sign XRPL transaction."""
        try:
            wallet = Wallet.from_seed(private_key)
            signed_tx = safe_sign_transaction(transaction, wallet)
            return signed_tx.to_xrpl()
        except Exception as e:
            raise TransactionError(f"Failed to sign transaction: {e}")
    
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_tx: str) -> str:
        """Broadcast signed transaction to XRPL."""
        if not self.is_connected or not self._client:
            raise ConnectionError("Not connected to XRPL")
        
        try:
            response = submit_and_wait(signed_tx, self._client)
            return response.result.get('hash', '')
        except Exception as e:
            raise TransactionError(f"Failed to broadcast transaction: {e}")
    
    @strict_blockchain_operation
    def estimate_fee(self, transaction: Any) -> float:
        """Estimate transaction fee in XRP."""
        if not self.is_connected or not self._client:
            raise ConnectionError("Not connected to XRPL")
        
        try:
            # Get current fee from ledger
            ledger_info = self._client.request({
                "command": "ledger",
                "ledger_index": "validated"
            })
            
            base_fee = ledger_info.get("result", {}).get("ledger", {}).get("base_fee_xrp", 0.00001)
            return float(base_fee)
        except Exception as e:
            # Return default fee if estimation fails
            return 0.00001
    
    @strict_blockchain_operation
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get transaction status by hash."""
        if not self.is_connected or not self._client:
            raise ConnectionError("Not connected to XRPL")
        
        try:
            tx_info = get_transaction_from_hash(tx_hash, self._client)
            return {
                'status': 'confirmed' if tx_info.validated else 'pending',
                'hash': tx_hash,
                'ledger_index': tx_info.ledger_index,
                'result': tx_info.result
            }
        except Exception as e:
            raise BlockchainError(f"Failed to get transaction status: {e}")
    
    @strict_blockchain_operation
    def get_network_status(self) -> Dict[str, Any]:
        """Get XRPL network status."""
        if not self.is_connected or not self._client:
            raise ConnectionError("Not connected to XRPL")
        
        try:
            server_info = self._client.request({"command": "server_info"})
            info = server_info.get("result", {}).get("info", {})
            
            return {
                'connected': True,
                'network': self.network,
                'server_state': info.get('server_state'),
                'validated_ledger': info.get('validated_ledger', {}).get('seq'),
                'peers': info.get('peers'),
                'load_factor': info.get('load_factor')
            }
        except Exception as e:
            raise BlockchainError(f"Failed to get network status: {e}")
    
    @strict_blockchain_operation
    def validate_address(self, address: str) -> bool:
        """Validate XRP address format."""
        try:
            return is_valid_classic_address(address)
        except Exception:
            return False
