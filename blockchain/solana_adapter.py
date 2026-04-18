#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Kingdom AI - Solana Blockchain Adapter

This module provides native, no-fallback integration with the Solana blockchain.
"""

import logging
import base58
from typing import Dict, Any, Optional, List, Union, Tuple
import json
import time
from pathlib import Path

# Import base adapter
from blockchain.base_adapter import (
    BlockchainAdapter, BlockchainError, ConnectionError, 
    TransactionError, ValidationError, strict_blockchain_operation
)

# Import Solana-specific libraries - 2026 SOTA: Graceful degradation
SOLANA_AVAILABLE = False
Client = None
Keypair = None
Transaction = None
PublicKey = None
Blockhash = None
Confirmed = "confirmed"
Finalized = "finalized"

try:
    # Try solders (modern Solana SDK)
    from solders.pubkey import Pubkey as PublicKey
    from solders.keypair import Keypair
    from solders.transaction import Transaction as SoldersTransaction
    from solders.hash import Hash as Blockhash
    
    # Try solana RPC client
    try:
        from solana.rpc.api import Client
        from solana.rpc.commitment import Confirmed, Finalized
        SOLANA_AVAILABLE = True
        Transaction = SoldersTransaction
        logging.getLogger(__name__).info("✅ Solana libraries loaded (solders + solana.rpc)")
    except ImportError:
        # solana.rpc not available - use httpx-based client
        import httpx
        class _MinimalSolanaClient:
            """Minimal Solana RPC client when solana.rpc is not available."""
            def __init__(self, endpoint: str):
                self.endpoint = endpoint
            def get_balance(self, pubkey):
                with httpx.Client() as client:
                    resp = client.post(self.endpoint, json={
                        "jsonrpc": "2.0", "id": 1, "method": "getBalance",
                        "params": [str(pubkey)]
                    })
                    return resp.json()
            def get_health(self):
                """Get health status of the Solana node (required by SolanaAdapter)."""
                try:
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.post(self.endpoint, json={
                            "jsonrpc": "2.0", "id": 1, "method": "getHealth"
                        })
                        if resp.status_code == 200:
                            return resp.json()  # Return full JSON response with "result" key
                        return {"result": "error", "error": f"HTTP {resp.status_code}"}
                except Exception as e:
                    return {"result": "error", "error": str(e)}
            
            def get_version(self):
                """Get Solana node version (required by SolanaAdapter)."""
                try:
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.post(self.endpoint, json={
                            "jsonrpc": "2.0", "id": 1, "method": "getVersion"
                        })
                        if resp.status_code == 200:
                            return resp.json()  # Return full JSON response
                        return {"error": f"HTTP {resp.status_code}"}
                except Exception as e:
                    return {"error": str(e)}
            
            def is_connected(self):
                try:
                    result = self.get_health()
                    if isinstance(result, dict):
                        return result.get("result") == "ok"
                    return False
                except Exception:
                    return False
        Client = _MinimalSolanaClient
        Transaction = SoldersTransaction
        SOLANA_AVAILABLE = True
        logging.getLogger(__name__).info("✅ Solana libraries loaded (solders + minimal RPC)")
except ImportError as e:
    logging.getLogger(__name__).info(f"ℹ️ Solana libraries not available: {e}")

# Set up logger
logger = logging.getLogger(__name__)

# RPC endpoints (production-grade with multiple options)
SOLANA_MAINNET_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-api.projectserum.com",
    "https://rpc.ankr.com/solana",
    "https://mainnet.rpcpool.com",
]

SOLANA_TESTNET_ENDPOINTS = [
    "https://api.testnet.solana.com",
    "https://testnet.rpcpool.com",
]

SOLANA_DEVNET_ENDPOINTS = [
    "https://api.devnet.solana.com",
    "https://devnet.rpcpool.com",
]

class SolanaAdapter(BlockchainAdapter[Transaction]):
    """Native Solana blockchain adapter with strict no-fallback policy."""
    
    def __init__(self, 
                 network: str = "mainnet", 
                 endpoints: Optional[List[str]] = None, 
                 commitment: str = "confirmed", 
                 config_path: Optional[str] = None):
        """Initialize Solana adapter.
        
        Args:
            network: Network to connect to ('mainnet', 'testnet', 'devnet')
            endpoints: Optional list of RPC endpoints (will override defaults if provided)
            commitment: Transaction commitment level ('processed', 'confirmed', 'finalized')
            config_path: Optional path to Solana config file
        """
        super().__init__(network_name=f"solana-{network}", chain_id=None)
        
        self.network = network.lower()
        self.commitment = commitment
        self.config_path = config_path
        self._client = None
        self._endpoints = endpoints or self._get_default_endpoints()
        self._current_endpoint_index = 0
        self._last_blockhash = None
        self._last_blockhash_time = 0
        
        # Connect immediately with strict validation
        self.connect()
        
    def _get_default_endpoints(self) -> List[str]:
        """Get default endpoints based on selected network."""
        if self.network == "mainnet":
            return SOLANA_MAINNET_ENDPOINTS
        elif self.network == "testnet":
            return SOLANA_TESTNET_ENDPOINTS
        elif self.network == "devnet":
            return SOLANA_DEVNET_ENDPOINTS
        else:
            raise ValueError(f"Unsupported Solana network: {self.network}")
            
    def _get_current_endpoint(self) -> str:
        """Get current endpoint from the endpoints list."""
        if not self._endpoints:
            raise ConnectionError("No Solana RPC endpoints available")
            
        return self._endpoints[self._current_endpoint_index % len(self._endpoints)]
    
    def _try_next_endpoint(self) -> None:
        """Try the next available endpoint in the list."""
        self._current_endpoint_index = (self._current_endpoint_index + 1) % len(self._endpoints)
        logger.warning(f"Switching to next Solana endpoint: {self._get_current_endpoint()}")
    
    @strict_blockchain_operation
    def connect(self) -> bool:
        """Connect to Solana network using available endpoints.
        
        Returns:
            bool: True if connected successfully
            
        Raises:
            ConnectionError: If all connection attempts fail
        """
        connection_errors = []
        
        # Try all endpoints until one works
        for _ in range(len(self._endpoints)):
            endpoint = self._get_current_endpoint()
            
            try:
                logger.info(f"Connecting to Solana {self.network} at {endpoint}")
                
                # Guard: If Client is None (solders/solana not installed), raise immediately
                if Client is None:
                    raise ConnectionError(
                        f"Solana client libraries not installed (solders/solana-py). "
                        f"Solana features disabled. Install with: pip install solders solana"
                    )
                
                # Initialize client with current endpoint
                self._client = Client(endpoint)
                
                # SOTA 2026: Test connection using get_version (get_health removed in newer solana-py)
                # get_version works on all Solana RPC nodes and validates connection
                try:
                    # Try get_health if available (older library versions)
                    if hasattr(self._client, 'get_health'):
                        health = self._client.get_health()
                        health_result = None
                        if isinstance(health, dict):
                            health_result = health.get("result")
                        elif isinstance(health, str):
                            health_result = health
                        elif hasattr(health, 'value'):
                            health_result = getattr(health, 'value', None)
                        if health_result != "ok":
                            raise ConnectionError(f"Solana health check failed: {health}")
                    else:
                        # Newer library: skip health check, get_version validates connection
                        logger.debug("get_health not available, using get_version for connection test")
                except Exception as e:
                    logger.debug(f"Health check skipped: {e}")
                    
                # Test connection with get_version to validate RPC functionality
                version = self._client.get_version()
                
                # Handle different response formats
                version_result = None
                if isinstance(version, dict):
                    version_result = version.get("result", version)
                elif hasattr(version, 'value'):  # GetVersionResp object
                    version_result = getattr(version, 'value', None)
                else:
                    version_result = version
                
                if not version_result:
                    raise ConnectionError("Failed to get Solana version")
                    
                # Log version information - handle both dict and object formats
                solana_version = "unknown"
                feature_set = "unknown"
                if isinstance(version_result, dict):
                    solana_version = version_result.get("solana-core", "unknown")
                    feature_set = version_result.get("feature-set", "unknown")
                elif hasattr(version_result, 'solana_core'):
                    solana_version = getattr(version_result, 'solana_core', 'unknown')
                    feature_set = getattr(version_result, 'feature_set', 'unknown')
                logger.info(f"Connected to Solana {self.network} (version {solana_version}, feature-set {feature_set})")
                
                self.is_connected = True
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to Solana endpoint {endpoint}: {str(e)}")
                connection_errors.append(f"{endpoint}: {str(e)}")
                self._try_next_endpoint()
        
        # If we get here, all connection attempts failed
        error_msg = f"Failed to connect to any Solana endpoint. Errors: {connection_errors}"
        logger.critical(error_msg)
        raise ConnectionError(error_msg)
    
    def _get_blockhash(self, force_refresh: bool = False) -> str:
        """Get a recent blockhash.
        
        Args:
            force_refresh: Force refresh of blockhash regardless of cache
            
        Returns:
            str: Recent blockhash
            
        Raises:
            ConnectionError: If unable to get blockhash
        """
        # Check if we need to refresh the blockhash (every 30 seconds)
        current_time = time.time()
        if force_refresh or not self._last_blockhash or (current_time - self._last_blockhash_time > 30):
            try:
                response = self._client.get_recent_blockhash(commitment=self.commitment)
                if "result" not in response or "value" not in response["result"]:
                    raise ConnectionError("Invalid response from get_recent_blockhash")
                    
                self._last_blockhash = response["result"]["value"]["blockhash"]
                self._last_blockhash_time = current_time
                
            except Exception as e:
                # Try to reconnect once
                self.connect()
                response = self._client.get_recent_blockhash(commitment=self.commitment)
                if "result" not in response or "value" not in response["result"]:
                    raise ConnectionError(f"Failed to get recent blockhash after reconnect: {str(e)}")
                self._last_blockhash = response["result"]["value"]["blockhash"]
                self._last_blockhash_time = current_time
                
        return self._last_blockhash
    
    @strict_blockchain_operation
    def get_balance(self, address: str, token_address: Optional[str] = None) -> float:
        """Get SOL balance for address or SPL token balance if token_address provided.
        
        Args:
            address: The address to check
            token_address: Optional SPL token address
            
        Returns:
            float: Balance in SOL or token units
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If address is invalid
        """
        if not self.is_connected:
            self.connect()
            
        try:
            # Validate address
            if not self.validate_address(address):
                raise ValidationError(f"Invalid Solana address: {address}")
                
            public_key = PublicKey(address)
            
            if token_address:
                # For SPL tokens
                try:
                    from spl.token.client import Token
                    from spl.token.constants import TOKEN_PROGRAM_ID
                    
                    token_public_key = PublicKey(token_address)
                    token_client = Token(
                        conn=self._client, 
                        pubkey=token_public_key, 
                        program_id=TOKEN_PROGRAM_ID, 
                        payer=None
                    )
                    
                    # Get token account info
                    token_accounts = token_client.get_accounts(owner=public_key)
                    
                    if not token_accounts:
                        return 0.0
                        
                    balance = sum(account.amount for account in token_accounts)
                    decimals = token_client.get_mint_info().decimals
                    
                    return balance / (10 ** decimals)
                    
                except ImportError:
                    raise ImportError("SPL token library not installed. Install with 'pip install spl-token'")
                except Exception as e:
                    raise ConnectionError(f"Failed to get token balance: {str(e)}")
            else:
                # For native SOL
                response = self._client.get_balance(public_key, commitment=self.commitment)
                
                if "result" not in response or "value" not in response["result"]:
                    raise ConnectionError("Invalid response from get_balance")
                    
                balance_lamports = response["result"]["value"]
                # Convert from lamports to SOL
                return balance_lamports / 1_000_000_000
                
        except ValidationError as e:
            # Re-raise validation errors
            raise e
        except Exception as e:
            raise ConnectionError(f"Failed to get balance: {str(e)}")
    
    @strict_blockchain_operation
    def create_transaction(self, **kwargs) -> Transaction:
        """Create a Solana transaction.
        
        Args:
            **kwargs: Transaction parameters:
                - sender (str): Sender address
                - recipient (str): Recipient address
                - amount (float): Amount in SOL
                - memo (str, optional): Transaction memo
                - token_address (str, optional): SPL token address for token transfers
                
        Returns:
            Transaction: Solana transaction object
            
        Raises:
            TransactionError: If transaction creation fails
            ValidationError: If parameters are invalid
        """
        if not self.is_connected:
            self.connect()
            
        # Extract and validate parameters
        sender = kwargs.get("sender")
        recipient = kwargs.get("recipient")
        amount = kwargs.get("amount")
        memo = kwargs.get("memo")
        token_address = kwargs.get("token_address")
        
        if not sender or not recipient:
            raise ValidationError("Sender and recipient addresses are required")
            
        if not self.validate_address(sender):
            raise ValidationError(f"Invalid sender address: {sender}")
            
        if not self.validate_address(recipient):
            raise ValidationError(f"Invalid recipient address: {recipient}")
            
        if amount is None or amount <= 0:
            raise ValidationError(f"Invalid amount: {amount}")
        
        try:
            sender_pubkey = PublicKey(sender)
            recipient_pubkey = PublicKey(recipient)
            
            # Get recent blockhash
            recent_blockhash = Blockhash(self._get_blockhash())
            
            if token_address:
                # SPL token transfer
                try:
                    from spl.token.constants import TOKEN_PROGRAM_ID
                    from spl.token.instructions import transfer, get_associated_token_address
                    
                    token_pubkey = PublicKey(token_address)
                    
                    # Convert amount to token units
                    decimals = self._get_token_decimals(token_pubkey)
                    amount_units = int(amount * (10 ** decimals))
                    
                    # Get associated token accounts
                    sender_token_account = get_associated_token_address(sender_pubkey, token_pubkey)
                    recipient_token_account = get_associated_token_address(recipient_pubkey, token_pubkey)
                    
                    # Create transfer instruction
                    transfer_ix = transfer(
                        TOKEN_PROGRAM_ID,
                        sender_token_account,
                        recipient_token_account,
                        sender_pubkey,
                        amount_units
                    )
                    
                    # Create transaction
                    transaction = Transaction(recent_blockhash=recent_blockhash)
                    transaction.add(transfer_ix)
                    
                except ImportError:
                    raise ImportError("SPL token library not installed. Install with 'pip install spl-token'")
                    
            else:
                # Native SOL transfer
                amount_lamports = int(amount * 1_000_000_000)  # Convert SOL to lamports
                
                # Create system transfer instruction
                transfer_ix = sp.transfer(
                    sp.TransferParams(
                        from_pubkey=sender_pubkey,
                        to_pubkey=recipient_pubkey,
                        lamports=amount_lamports
                    )
                )
                
                # Create transaction
                transaction = Transaction(recent_blockhash=recent_blockhash)
                transaction.add(transfer_ix)
                
            # Add memo if provided
            if memo:
                from spl.memo.instructions import create_memo
                memo_ix = create_memo(sender_pubkey, memo)
                transaction.add(memo_ix)
                
            return transaction
            
        except ImportError as e:
            raise ImportError(f"Required library not installed: {str(e)}")
        except Exception as e:
            raise TransactionError(f"Failed to create transaction: {str(e)}")
    
    def _get_token_decimals(self, token_pubkey: PublicKey) -> int:
        """Get token decimals for a SPL token.
        
        Args:
            token_pubkey: Token public key
            
        Returns:
            int: Token decimals
            
        Raises:
            ConnectionError: If unable to get token info
        """
        try:
            # Get token mint info to determine decimals
            response = self._client.get_account_info(token_pubkey)
            
            if "result" not in response or "value" not in response["result"]:
                raise ConnectionError("Invalid response when getting token info")
                
            # Parse mint data to get decimals
            from spl.token.client import Token
            from spl.token.constants import TOKEN_PROGRAM_ID
            
            token_client = Token(
                conn=self._client,
                pubkey=token_pubkey,
                program_id=TOKEN_PROGRAM_ID,
                payer=None
            )
            
            mint_info = token_client.get_mint_info()
            return mint_info.decimals
            
        except Exception as e:
            raise ConnectionError(f"Failed to get token decimals: {str(e)}")
    
    @strict_blockchain_operation
    def sign_transaction(self, transaction: Transaction, private_key: str) -> Transaction:
        """Sign Solana transaction with private key.
        
        Args:
            transaction: Transaction to sign
            private_key: Base58 encoded private key or path to keypair file
            
        Returns:
            Transaction: Signed transaction
            
        Raises:
            TransactionError: If transaction signing fails
        """
        try:
            # Handle private key input
            if private_key.startswith("file:"):
                # Load from file
                file_path = private_key.replace("file:", "", 1)
                with open(file_path, "r") as f:
                    keypair_data = json.load(f)
                    keypair = Keypair.from_secret_key(bytes(keypair_data))
            elif len(private_key) == 88:  # Length of base58 encoded keypair
                keypair_bytes = base58.b58decode(private_key)
                keypair = Keypair.from_secret_key(keypair_bytes)
            elif len(private_key) == 64:  # Length of hex encoded private key
                keypair_bytes = bytes.fromhex(private_key)
                keypair = Keypair.from_secret_key(keypair_bytes)
            else:
                try:
                    from solders.keypair import Keypair as SoldersKeypair
                    keypair = SoldersKeypair.from_seed_phrase(private_key)
                except Exception:
                    raise TransactionError(
                        "Cannot parse seed phrase: install solders>=0.20 or provide a hex/base58 private key"
                    )
            
            # Sign the transaction
            transaction.sign([keypair])
            
            return transaction
            
        except Exception as e:
            raise TransactionError(f"Failed to sign transaction: {str(e)}")
    
    @strict_blockchain_operation
    def broadcast_transaction(self, signed_transaction: Transaction) -> str:
        """Broadcast signed Solana transaction.
        
        Args:
            signed_transaction: Signed transaction to broadcast
            
        Returns:
            str: Transaction signature (hash)
            
        Raises:
            TransactionError: If broadcasting fails
            ConnectionError: If network connection is lost
        """
        if not self.is_connected:
            self.connect()
            
        try:
            # Convert transaction to wire format
            tx_wire_format = signed_transaction.serialize()
            
            # Set transaction options
            opts = TxOpts(skip_confirmation=False, preflight_commitment=self.commitment)
            
            # Send transaction
            response = self._client.send_transaction(tx_wire_format, opts=opts)
            
            if "result" not in response:
                # Check for error
                if "error" in response:
                    error_code = response["error"].get("code", "unknown")
                    error_msg = response["error"].get("message", "Unknown error")
                    raise TransactionError(f"Transaction failed with code {error_code}: {error_msg}")
                else:
                    raise TransactionError("Invalid response from send_transaction")
                    
            tx_signature = response["result"]
            logger.info(f"Broadcast Solana transaction: {tx_signature}")
            
            return tx_signature
            
        except Exception as e:
            # Try to reconnect once on connection errors
            if "connection" in str(e).lower():
                self.connect()
                
                # Retry with fresh blockhash
                signed_transaction.recent_blockhash = Blockhash(self._get_blockhash(force_refresh=True))
                
                tx_wire_format = signed_transaction.serialize()
                opts = TxOpts(skip_confirmation=False, preflight_commitment=self.commitment)
                response = self._client.send_transaction(tx_wire_format, opts=opts)
                
                if "result" not in response:
                    error_details = response.get("error", {})
                    error_msg = error_details.get("message", "Unknown error")
                    raise TransactionError(f"Transaction retry failed: {error_msg}")
                    
                tx_signature = response["result"]
                logger.info(f"Broadcast Solana transaction (retry): {tx_signature}")
                return tx_signature
                
            raise TransactionError(f"Failed to broadcast transaction: {str(e)}")
    
    @strict_blockchain_operation
    def validate_address(self, address: str) -> bool:
        """Validate Solana address format.
        
        Args:
            address: Address to validate
            
        Returns:
            bool: True if address is valid, False otherwise
        """
        try:
            PublicKey(address)
            return True
        except ValueError:
            return False
    
    @strict_blockchain_operation
    def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get status of Solana transaction.
        
        Args:
            tx_hash: Transaction signature
            
        Returns:
            dict: Transaction status details
            
        Raises:
            ConnectionError: If network connection fails
            ValidationError: If tx_hash is invalid
        """
        if not self.is_connected:
            self.connect()
            
        try:
            response = self._client.get_transaction(
                tx_sig=tx_hash,
                commitment=Finalized
            )
            
            if "result" not in response:
                # Check if transaction not found
                if "error" in response and "not found" in str(response["error"]).lower():
                    return {
                        "found": False,
                        "confirmed": False,
                        "confirmations": 0
                    }
                # Other errors
                raise ConnectionError(f"Failed to get transaction status: {response.get('error')}")
                
            result = response["result"]
            meta = result.get("meta", {})
            
            # Extract status information
            status = {
                "found": True,
                "confirmed": True,
                "confirmations": result.get("confirmations", 0),
                "slot": result.get("slot"),
                "blockTime": result.get("blockTime"),
                "err": meta.get("err"),
                "fee": meta.get("fee"),
                "status": "success" if meta.get("err") is None else "failed"
            }
            
            # Add human-readable timestamp if blockTime exists
            if result.get("blockTime"):
                from datetime import datetime
                status["timestamp"] = datetime.fromtimestamp(result["blockTime"]).isoformat()
                
            return status
            
        except Exception as e:
            raise ConnectionError(f"Failed to get transaction status: {str(e)}")
    
    @strict_blockchain_operation
    def get_network_status(self) -> Dict[str, Any]:
        """Get Solana network status.
        
        Returns:
            dict: Network status including block height, sync state, etc.
            
        Raises:
            ConnectionError: If network connection fails
        """
        if not self.is_connected:
            self.connect()
            
        try:
            # Get cluster nodes information
            nodes_response = self._client.get_cluster_nodes()
            
            # Get epoch information
            epoch_info_response = self._client.get_epoch_info()
            
            # Get validators
            validators_response = self._client.get_validators()
            
            # Get slot
            slot_response = self._client.get_slot()
            
            # Get vote accounts
            vote_accounts_response = self._client.get_vote_accounts()
            
            # Combine into comprehensive status
            status = {
                "network": self.network,
                "endpoint": self._get_current_endpoint(),
                "slot": slot_response.get("result"),
                "epoch": epoch_info_response.get("result", {}).get("epoch"),
                "epochProgress": epoch_info_response.get("result", {}).get("slotIndex") / 
                               max(1, epoch_info_response.get("result", {}).get("slotsInEpoch", 1)) * 100,
                "nodes": len(nodes_response.get("result", [])),
                "validators": {
                    "active": len(validators_response.get("result", {}).get("current", [])),
                    "total": len(validators_response.get("result", {}).get("current", [])) + 
                           len(validators_response.get("result", {}).get("delinquent", []))
                },
                "voting": {
                    "current": len(vote_accounts_response.get("result", {}).get("current", [])),
                    "delinquent": len(vote_accounts_response.get("result", {}).get("delinquent", []))
                }
            }
            
            return status
            
        except Exception as e:
            raise ConnectionError(f"Failed to get network status: {str(e)}")
    
    @strict_blockchain_operation
    def estimate_fee(self, transaction: Transaction) -> Dict[str, Any]:
        """Estimate fee for Solana transaction.
        
        Args:
            transaction: Transaction to estimate fee for
            
        Returns:
            dict: Fee estimation details
            
        Raises:
            ConnectionError: If network connection fails
            TransactionError: If fee estimation fails
        """
        if not self.is_connected:
            self.connect()
            
        try:
            # Convert transaction to wire format
            tx_wire_format = transaction.serialize()
            
            # Get fee estimate
            response = self._client.get_fee_for_message(tx_wire_format)
            
            if "result" not in response or "value" not in response["result"]:
                raise ConnectionError("Invalid response when estimating fee")
                
            fee_lamports = response["result"]["value"]
            
            return {
                "estimated_fee_lamports": fee_lamports,
                "estimated_fee_sol": fee_lamports / 1_000_000_000
            }
            
        except Exception as e:
            raise TransactionError(f"Failed to estimate fee: {str(e)}")
