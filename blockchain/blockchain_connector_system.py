#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Kingdom AI - Blockchain Connector System

This module provides integration between the blockchain registry and the Kingdom AI system.
It ensures all components use 100% native, no-fallback blockchain support through the registry.
"""

import logging
import time
import json
from typing import Dict, Any, Optional, List, Union

# Import blockchain registry
from blockchain.blockchain_registry import get_registry, BlockchainRegistry
from blockchain.base_adapter import BlockchainError, ConnectionError, TransactionError, ValidationError

# Import event system for Kingdom AI integration
from core.event_bus import EventBus
from utils.config_manager import ConfigManager

# Set up logger
logger = logging.getLogger(__name__)

class BlockchainConnectorSystem:
    """
    System-wide connector for blockchain functionality.
    Ensures 100% native, no-fallback integration with all Kingdom AI components.
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the blockchain connector system.
        
        Args:
            event_bus: Kingdom AI event bus
        """
        self._event_bus = event_bus
        self._config = ConfigManager().get_config("blockchain_config")
        self._registry = self._initialize_registry()
        self._active_chains = {}
        self._blockchain_statuses = {}
        self._last_status_check = 0
        self._status_check_interval = 30  # seconds
        
        # Register event handlers
        self._register_events()
        
        # Initialize all blockchain adapters
        self._initialize_adapters()
        
    def _initialize_registry(self) -> BlockchainRegistry:
        """
        Initialize the blockchain registry with Redis Quantum Nexus connection.
        
        Returns:
            BlockchainRegistry: The initialized registry
            
        Raises:
            SystemExit: If registry initialization fails (no fallback allowed)
        """
        try:
            # Get Redis connection parameters from config
            redis_config = ConfigManager().get_config("redis_config")
            redis_host = redis_config.get("host", "localhost")
            redis_port = redis_config.get("port", 6380)  # Default to required port
            redis_password = redis_config.get("password", "QuantumNexus2025")
            
            # Validate Redis configuration
            if redis_port != 6380:
                error_msg = f"Invalid Redis port: {redis_port}. Required port is 6380."
                logger.critical(error_msg)
                raise SystemExit(error_msg)
                
            # Initialize registry
            registry = get_registry(
                redis_host=redis_host,
                redis_port=redis_port,
                redis_password=redis_password
            )
            
            return registry
            
        except Exception as e:
            error_msg = f"Failed to initialize blockchain registry: {str(e)}"
            logger.critical(error_msg)
            # No fallback - system must halt if registry initialization fails
            raise SystemExit(error_msg)
    
    def _register_events(self) -> None:
        """
        Register event handlers for blockchain events.
        """
        # Register blockchain-related events
        self._event_bus.register("blockchain.get_status", self.get_blockchain_status)
        self._event_bus.register("blockchain.get_balance", self.get_balance)
        self._event_bus.register("blockchain.create_transaction", self.create_transaction)
        self._event_bus.register("blockchain.sign_transaction", self.sign_transaction)
        self._event_bus.register("blockchain.broadcast_transaction", self.broadcast_transaction)
        self._event_bus.register("blockchain.validate_address", self.validate_address)
        self._event_bus.register("blockchain.get_transaction", self.get_transaction)
        self._event_bus.register("blockchain.get_block", self.get_block)
        self._event_bus.register("blockchain.refresh_config", self.refresh_config)
        
        # System events
        self._event_bus.register("system.startup", self.on_system_startup)
        self._event_bus.register("system.shutdown", self.on_system_shutdown)
        
    def _initialize_adapters(self) -> None:
        """
        Initialize all enabled blockchain adapters.
        
        Raises:
            SystemExit: If initialization of required adapters fails (no fallback allowed)
        """
        try:
            # Initialize all adapters through the registry
            self._registry.initialize_adapters()
            
            # Get enabled chains
            enabled_chains = self._registry.get_enabled_chains()
            logger.info(f"Initialized {len(enabled_chains)} blockchain adapters: {', '.join(enabled_chains)}")
            
            # Check blockchain statuses
            self.update_blockchain_statuses()
            
        except Exception as e:
            error_msg = f"Failed to initialize blockchain adapters: {str(e)}"
            logger.critical(error_msg)
            # No fallback - system must halt if adapter initialization fails
            raise SystemExit(error_msg)
    
    def update_blockchain_statuses(self) -> Dict[str, Dict[str, Any]]:
        """
        Update status of all enabled blockchains.
        
        Returns:
            Dict[str, Dict[str, Any]]: Status information for each chain
        """
        current_time = time.time()
        
        # Only update if enough time has passed since last check
        if current_time - self._last_status_check < self._status_check_interval:
            return self._blockchain_statuses
            
        try:
            # Get status of all chains
            self._blockchain_statuses = self._registry.get_all_chain_statuses()
            self._last_status_check = current_time
            
            # Emit event with updated statuses
            self._event_bus.emit("blockchain.status_updated", self._blockchain_statuses)
            
            return self._blockchain_statuses
            
        except Exception as e:
            error_msg = f"Failed to update blockchain statuses: {str(e)}"
            logger.error(error_msg)
            # Return last known statuses
            return self._blockchain_statuses
    
    def get_blockchain_status(self, chain_id: str) -> Dict[str, Any]:
        """
        Get status of a specific blockchain.
        
        Args:
            chain_id: Blockchain identifier
            
        Returns:
            Dict[str, Any]: Status information
        """
        # Update statuses if needed
        current_time = time.time()
        if current_time - self._last_status_check > self._status_check_interval:
            self.update_blockchain_statuses()
            
        # Return status for the requested chain
        if chain_id in self._blockchain_statuses:
            return self._blockchain_statuses[chain_id]
        else:
            return {"error": f"Chain {chain_id} not found", "connected": False}
    
    def get_balance(self, chain_id: str, address: str, token_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Get balance for an address on the specified blockchain.
        
        Args:
            chain_id: Blockchain identifier
            address: The address to check
            token_address: Optional token address for token balances
            
        Returns:
            Dict[str, Any]: Balance information
        """
        try:
            adapter = self._registry.get_adapter(chain_id)
            balance = adapter.get_balance(address, token_address)
            
            return {
                "chain_id": chain_id,
                "address": address,
                "balance": balance,
                "token_address": token_address,
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Failed to get balance for {address} on {chain_id}: {str(e)}"
            logger.error(error_msg)
            
            return {
                "chain_id": chain_id,
                "address": address,
                "balance": 0,
                "token_address": token_address,
                "success": False,
                "error": str(e)
            }
    
    def create_transaction(self, chain_id: str, **kwargs) -> Dict[str, Any]:
        """
        Create a transaction on the specified blockchain.
        
        Args:
            chain_id: Blockchain identifier
            **kwargs: Transaction parameters
            
        Returns:
            Dict[str, Any]: Transaction information
        """
        try:
            adapter = self._registry.get_adapter(chain_id)
            transaction = adapter.create_transaction(**kwargs)
            
            return {
                "chain_id": chain_id,
                "transaction": transaction,
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Failed to create transaction on {chain_id}: {str(e)}"
            logger.error(error_msg)
            
            return {
                "chain_id": chain_id,
                "success": False,
                "error": str(e)
            }
    
    def sign_transaction(self, chain_id: str, transaction: Any, private_key: str) -> Dict[str, Any]:
        """
        Sign a transaction on the specified blockchain.
        
        Args:
            chain_id: Blockchain identifier
            transaction: The transaction to sign
            private_key: Private key to sign with
            
        Returns:
            Dict[str, Any]: Signed transaction information
        """
        try:
            adapter = self._registry.get_adapter(chain_id)
            signed_tx = adapter.sign_transaction(transaction, private_key)
            
            return {
                "chain_id": chain_id,
                "signed_transaction": signed_tx,
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Failed to sign transaction on {chain_id}: {str(e)}"
            logger.error(error_msg)
            
            return {
                "chain_id": chain_id,
                "success": False,
                "error": str(e)
            }
    
    def broadcast_transaction(self, chain_id: str, signed_transaction: Any) -> Dict[str, Any]:
        """
        Broadcast a signed transaction on the specified blockchain.
        
        Args:
            chain_id: Blockchain identifier
            signed_transaction: The signed transaction to broadcast
            
        Returns:
            Dict[str, Any]: Transaction broadcast information
        """
        try:
            adapter = self._registry.get_adapter(chain_id)
            tx_hash = adapter.broadcast_transaction(signed_transaction)

            # Emit event for successful transaction
            self._event_bus.emit("blockchain.transaction_broadcast", {
                "chain_id": chain_id,
                "tx_hash": tx_hash,
                "success": True
            })

            # Emit lightweight telemetry for observability
            self._event_bus.emit(
                "blockchain.telemetry",
                {
                    "component": "blockchain",
                    "channel": "blockchain.telemetry",
                    "event_type": "transaction_broadcast",
                    "timestamp": datetime.now().isoformat(),
                    "success": True,
                    "error": None,
                    "metadata": {
                        "chain_id": chain_id,
                        "tx_hash": tx_hash,
                    },
                },
            )

            return {
                "chain_id": chain_id,
                "tx_hash": tx_hash,
                "success": True
            }

        except Exception as e:
            error_msg = f"Failed to broadcast transaction on {chain_id}: {str(e)}"
            logger.error(error_msg)

            # Emit event for failed transaction
            self._event_bus.emit("blockchain.transaction_failed", {
                "chain_id": chain_id,
                "error": str(e),
                "success": False
            })

            # Emit telemetry for the failure as well
            try:
                self._event_bus.emit(
                    "blockchain.telemetry",
                    {
                        "component": "blockchain",
                        "channel": "blockchain.telemetry",
                        "event_type": "transaction_broadcast",
                        "timestamp": datetime.now().isoformat(),
                        "success": False,
                        "error": str(e),
                        "metadata": {
                            "chain_id": chain_id,
                        },
                    },
                )
            except Exception:
                # Never raise from telemetry path
                pass

            return {
                "chain_id": chain_id,
                "success": False,
                "error": str(e)
            }
    
    def validate_address(self, chain_id: str, address: str) -> Dict[str, Any]:
        """
        Validate an address on the specified blockchain.
        
        Args:
            chain_id: Blockchain identifier
            address: The address to validate
            
        Returns:
            Dict[str, Any]: Validation information
        """
        try:
            adapter = self._registry.get_adapter(chain_id)
            is_valid = adapter.validate_address(address)
            
            return {
                "chain_id": chain_id,
                "address": address,
                "valid": is_valid,
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Failed to validate address {address} on {chain_id}: {str(e)}"
            logger.error(error_msg)
            
            return {
                "chain_id": chain_id,
                "address": address,
                "valid": False,
                "success": False,
                "error": str(e)
            }
    
    def get_transaction(self, chain_id: str, tx_hash: str) -> Dict[str, Any]:
        """
        Get transaction details from the specified blockchain.
        
        Args:
            chain_id: Blockchain identifier
            tx_hash: Transaction hash
            
        Returns:
            Dict[str, Any]: Transaction details
        """
        try:
            adapter = self._registry.get_adapter(chain_id)
            tx_data = adapter.get_transaction(tx_hash)
            
            return {
                "chain_id": chain_id,
                "tx_hash": tx_hash,
                "tx_data": tx_data,
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Failed to get transaction {tx_hash} on {chain_id}: {str(e)}"
            logger.error(error_msg)
            
            return {
                "chain_id": chain_id,
                "tx_hash": tx_hash,
                "success": False,
                "error": str(e)
            }
    
    def get_block(self, chain_id: str, block_id: Union[str, int]) -> Dict[str, Any]:
        """
        Get block details from the specified blockchain.
        
        Args:
            chain_id: Blockchain identifier
            block_id: Block hash or number
            
        Returns:
            Dict[str, Any]: Block details
        """
        try:
            adapter = self._registry.get_adapter(chain_id)
            block_data = adapter.get_block(block_id)
            
            return {
                "chain_id": chain_id,
                "block_id": block_id,
                "block_data": block_data,
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Failed to get block {block_id} on {chain_id}: {str(e)}"
            logger.error(error_msg)
            
            return {
                "chain_id": chain_id,
                "block_id": block_id,
                "success": False,
                "error": str(e)
            }
    
    def refresh_config(self) -> Dict[str, Any]:
        """
        Refresh blockchain configurations from Redis.
        
        Returns:
            Dict[str, Any]: Refresh status information
        """
        try:
            self._registry.refresh_config()
            
            # Re-initialize adapters with new configs
            self._initialize_adapters()
            
            return {
                "success": True,
                "message": "Blockchain configurations refreshed successfully"
            }
            
        except Exception as e:
            error_msg = f"Failed to refresh blockchain configurations: {str(e)}"
            logger.critical(error_msg)
            
            return {
                "success": False,
                "error": str(e)
            }
    
    def on_system_startup(self, data: Dict[str, Any]) -> None:
        """
        Handle system startup event.
        
        Args:
            data: Event data
        """
        logger.info("BlockchainConnectorSystem initializing on system startup")
        self._initialize_adapters()
        
    def on_system_shutdown(self, data: Dict[str, Any]) -> None:
        """
        Handle system shutdown event.
        
        Args:
            data: Event data
        """
        logger.info("BlockchainConnectorSystem shutting down")
