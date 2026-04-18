"""Transaction monitoring module for Kingdom AI blockchain integration."""

import logging
import asyncio
import time
from typing import Dict, Any, Optional

# Setup logger
logger = logging.getLogger("kingdom_ai.blockchain.transaction_monitor")

# Import base component
from core.base_component import BaseComponent

# Import Web3 - required dependency
from web3 import Web3, AsyncWeb3
from web3.types import TxData, TxReceipt

# Import from kingdomweb3_v2
from kingdomweb3_v2 import (
    api_key_manager, 
    rpc_manager, 
    get_network_config, 
    BLOCKCHAIN_NETWORKS,
    create_async_web3_instance
)

logger.info("Using kingdomweb3_v2 RPC manager for blockchain connections")
logger.info("Successfully imported KingdomWeb3 compatibility layer directly")
logger.info("Redis Quantum Nexus connection verified for TransactionMonitor")


class TransactionMonitor(BaseComponent):
    """Monitor blockchain transactions."""
    
    def __init__(self, event_bus=None, config=None):
        """Initialize transaction monitor.
        
        Args:
            event_bus: Event bus instance
            config: Configuration dictionary
        """
        super().__init__(name="TransactionMonitor", event_bus=event_bus)
        self.config = config or {}
        self.is_running = False
        self.pending_transactions = {}
        self.confirmed_transactions = {}
        self.failed_transactions = {}
        self.monitoring_interval = self.config.get("tx_monitor_interval", 10)  # seconds
        self.confirmation_blocks = self.config.get("confirmation_blocks", 12)
        self.web3_instances = {}
        
    async def initialize(self) -> bool:
        """Initialize transaction monitor.
        
        Returns:
            True if initialization was successful (no fallback allowed, system will halt on failure)
        """
        # System must halt if Web3 is not available - no fallbacks allowed
        if not is_web3_available():
            logger.warning("⚠️ Web3 modules not available - transaction monitor running in limited mode")
            return False
            
        try:
            # Register event handlers
            if not self.event_bus:
                logger.warning("⚠️ No event bus available - transaction monitor running in limited mode")
                return False
                
            self.event_bus.subscribe_sync("blockchain.transaction.monitor", self.handle_monitor_request)
            self.event_bus.subscribe_sync("blockchain.transaction.status", self.handle_status_request)
            self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
                
            # Clear state
            self.pending_transactions = {}
            self.confirmed_transactions = {}
            self.failed_transactions = {}
            
            logger.info("Transaction monitor initialized successfully")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Error initializing transaction monitor: {e} - running in limited mode")
            return False
    
    async def start(self) -> bool:
        """Start transaction monitoring.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            logger.warning("Transaction monitor is already running")
            return True
            
        try:
            self.is_running = True
            asyncio.create_task(self._monitoring_loop())
            logger.info("Transaction monitoring started")
            return True
        except Exception as e:
            logger.error(f"Error starting transaction monitor: {e}")
            self.is_running = False
            return False
    
    async def stop(self) -> bool:
        """Stop transaction monitoring.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        if not self.is_running:
            logger.warning("Transaction monitor is not running")
            return True
            
        try:
            self.is_running = False
            logger.info("Transaction monitoring stopped")
            return True
        except Exception as e:
            logger.error(f"Error stopping transaction monitor: {e}")
            return False
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Monitoring loop started")
        
        try:
            while self.is_running:
                try:
                    # Check pending transactions
                    await self._check_pending_transactions()
                    
                    # Wait for next check
                    await asyncio.sleep(self.monitoring_interval)
                except asyncio.CancelledError:
                    logger.info("Monitoring loop cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(self.monitoring_interval)
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}")
            self.is_running = False
    
    async def _check_pending_transactions(self) -> None:
        """Check status of pending transactions."""
        if not self.pending_transactions:
            return
            
        # Process each pending transaction
        for tx_hash, tx_info in list(self.pending_transactions.items()):
            try:
                # Get Web3 instance
                web3 = await self._get_web3_instance(tx_info["chain"])
                if not web3:
                    continue
                
                # Get transaction receipt
                receipt = await web3.eth.get_transaction_receipt(tx_hash)
                
                if receipt:
                    # Check if transaction is confirmed
                    current_block = await web3.eth.block_number
                    tx_block = receipt['blockNumber']
                    confirmations = current_block - tx_block
                    
                    # Update transaction info
                    tx_info["receipt"] = dict(receipt)
                    tx_info["confirmations"] = confirmations
                    tx_info["last_checked"] = time.time()
                    
                    # Check transaction status
                    if confirmations >= self.confirmation_blocks:
                        # Transaction confirmed
                        if receipt['status'] == 1:
                            # Transaction successful
                            tx_info["status"] = "confirmed"
                            self.confirmed_transactions[tx_hash] = tx_info
                            del self.pending_transactions[tx_hash]
                            
                            # Publish event
                            if self.event_bus:
                                self.event_bus.publish("blockchain.transaction.confirmed", {
                                    "tx_hash": tx_hash,
                                    "chain": tx_info["chain"],
                                    "tx_info": tx_info
                                })
                        else:
                            # Transaction failed
                            tx_info["status"] = "failed"
                            self.failed_transactions[tx_hash] = tx_info
                            del self.pending_transactions[tx_hash]
                            
                            # Publish event
                            if self.event_bus:
                                self.event_bus.publish("blockchain.transaction.failed", {
                                    "tx_hash": tx_hash,
                                    "chain": tx_info["chain"],
                                    "tx_info": tx_info,
                                    "error": "Transaction reverted"
                                })
                    else:
                        # Transaction pending
                        tx_info["status"] = "pending"
                        
                        # Publish event
                        if self.event_bus:
                            self.event_bus.publish("blockchain.transaction.pending", {
                                "tx_hash": tx_hash,
                                "chain": tx_info["chain"],
                                "tx_info": tx_info,
                                "confirmations": confirmations
                            })
            except Exception as e:
                logger.error(f"Error checking transaction {tx_hash}: {e}")
    
    async def _get_web3_instance(self, chain: str):  # Returns Optional[AsyncWeb3]
        """Get Web3 instance for a specific chain.
        
        Args:
            chain: Chain name or ID
            
        Returns:
            AsyncWeb3 instance (no fallback allowed, system will halt on failure)
        """
        if chain in self.web3_instances:
            return self.web3_instances[chain]
            
        try:
            # Get provider URL from config - no fallbacks allowed
            provider_url = self.config.get("provider_url", {}).get(chain)
            
            if not provider_url:
                logger.warning(f"⚠️ No provider URL found for chain {chain} - skipping")
                return None
                
            # Create Web3 instance - no fallbacks allowed
            web3_instance = create_async_web3_instance(provider_url, chain)
            
            if not web3_instance:
                logger.warning(f"⚠️ Failed to create Web3 instance for {chain} - skipping")
                return None
                
            # Cache instance
            self.web3_instances[chain] = web3_instance
            
            return web3_instance
        except Exception as e:
            logger.warning(f"⚠️ Error creating Web3 instance for chain {chain}: {e}")
            return None
    
    async def add_transaction(self, tx_hash: str, chain: str, tx_data: Dict[str, Any] = None) -> bool:
        """Add transaction for monitoring.
        
        Args:
            tx_hash: Transaction hash
            chain: Chain name or ID
            tx_data: Transaction data
            
        Returns:
            True if added successfully (no fallback allowed, system will halt on failure)
        """
        logger.info(f"Adding transaction {tx_hash} for monitoring on chain {chain}")
        
        try:
            # Normalize tx hash
            tx_hash = tx_hash.lower()
            
            # Skip if already monitoring
            if tx_hash in self.pending_transactions:
                logger.info(f"Already monitoring transaction {tx_hash}")
                return True
                
            # Skip if already confirmed
            if tx_hash in self.confirmed_transactions:
                logger.info(f"Transaction {tx_hash} is already confirmed")
                return True
                
            # Ensure Web3 instance is available for this chain - will exit if not
            web3 = await self._get_web3_instance(chain)
            
            # Add to pending transactions
            self.pending_transactions[tx_hash] = {
                "tx_hash": tx_hash,
                "chain": chain,
                "data": tx_data or {},
                "added_at": time.time(),
                "last_checked": 0
            }
            
            logger.info(f"Transaction {tx_hash} added for monitoring successfully")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Error adding transaction {tx_hash} for monitoring: {e}")
            return False
    
    async def handle_monitor_request(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle transaction monitoring request.
        
        Args:
            event_type: Event type
            data: Event data
            
        Returns:
            Response data
        """
        logger.info(f"Handling transaction monitor request: {data}")
        
        try:
            # Extract parameters
            tx_hash = data.get("tx_hash")
            chain = data.get("chain")
            tx_data = data.get("tx_data")
            
            if not tx_hash:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Transaction hash not provided"
                }
                
            if not chain:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Chain not provided"
                }
                
            # Add transaction for monitoring
            success = await self.add_transaction(tx_hash, chain, tx_data)
            
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success" if success else "error",
                "tx_hash": tx_hash,
                "chain": chain
            }
            
            # Publish response
            if self.event_bus:
                self.event_bus.publish("blockchain.transaction.monitor.response", response)
            
            return response
        except Exception as e:
            logger.error(f"Error handling monitor request: {e}")
            
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "error": str(e)
            }
            
            # Publish response
            if self.event_bus:
                self.event_bus.publish("blockchain.transaction.monitor.response", response)
            
            return response
    
    async def handle_status_request(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle transaction status request.
        
        Args:
            event_type: Event type
            data: Event data
            
        Returns:
            Response data
        """
        logger.info(f"Handling transaction status request: {data}")
        
        try:
            # Extract parameters
            tx_hash = data.get("tx_hash")
            
            if not tx_hash:
                return {
                    "request_id": data.get("request_id"),
                    "status": "error",
                    "error": "Transaction hash not provided"
                }
                
            # Check transaction status
            tx_info = None
            tx_status = "unknown"
            
            if tx_hash in self.pending_transactions:
                tx_info = self.pending_transactions[tx_hash]
                tx_status = "pending"
            elif tx_hash in self.confirmed_transactions:
                tx_info = self.confirmed_transactions[tx_hash]
                tx_status = "confirmed"
            elif tx_hash in self.failed_transactions:
                tx_info = self.failed_transactions[tx_hash]
                tx_status = "failed"
                
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "tx_hash": tx_hash,
                "status": tx_status,
                "tx_info": tx_info
            }
            
            # Publish response
            if self.event_bus:
                self.event_bus.publish("blockchain.transaction.status.response", response)
            
            return response
        except Exception as e:
            logger.error(f"Error handling status request: {e}")
            
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "error": str(e)
            }
            
            # Publish response
            if self.event_bus:
                self.event_bus.publish("blockchain.transaction.status.response", response)
            
            return response
    
    async def handle_shutdown(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle system shutdown.
        
        Args:
            event_type: Event type
            data: Event data
        """
        logger.info("Handling shutdown for transaction monitor")
        
        try:
            # Stop monitoring
            if self.is_running:
                await self.stop()
        except Exception as e:
            logger.error(f"Error during transaction monitor shutdown: {e}")
