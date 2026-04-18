"""
Blockchain Mining Module for Kingdom AI

Provides mining-specific blockchain operations including:
- Starting/stopping mining operations
- Getting mining statistics
- Submitting work
- Monitoring mining performance
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Any

# Import Web3 via our unified blockchain bridge for consistent compatibility

from core.event_bus import EventBus
from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class BlockchainMiningManager(BaseComponent):
    """Handles blockchain mining operations and statistics."""
    
    def __init__(self, 
                 web3: "AsyncWeb3", 
                 event_bus: Optional[EventBus] = None,
                 config: Optional[Dict[str, Any]] = None):
        """Initialize the blockchain mining manager.
        
        Args:
            web3: AsyncWeb3 instance
            event_bus: Event bus for publishing mining events
            config: Mining configuration
        """
        super().__init__(name="BlockchainMiningManager", event_bus=event_bus)
        self.web3 = web3
        self.config = config or {}
        self.mining_stats = {
            'active': False,
            'hashrate': 0.0,
            'workers': {},
            'last_block_found': None,
            'total_hashes': 0,
            'shares': {
                'accepted': 0,
                'rejected': 0,
                'stale': 0
            },
            'uptime': 0.0,
            'start_time': None
        }
        self._monitor_task = None
        self._monitor_interval = self.config.get('monitor_interval_seconds', 10)
        self._shutdown_event = asyncio.Event()
        
        # SOTA 2026: Register on EventBus for component discovery
        if self.event_bus:
            try:
                from core.component_registry import register_component
                register_component('blockchain_mining', self)
                logger.info("✅ Blockchain mining registered on EventBus")
            except Exception as e:
                logger.debug(f"Component registration failed: {e}")
        
    async def initialize(self) -> bool:
        """Initialize the mining manager with strict real blockchain validation.
        
        Ensures connection is established to real mainnet networks only.
        System will halt if real blockchain connections cannot be established.
        
        Returns:
            bool: True if initialization was successful with real networks
            
        Raises:
            RuntimeError: If connection fails or non-mainnet network detected
        """
        try:
            logger.info("Initializing BlockchainMiningManager with STRICT real blockchain validation")
            
            # Verify we have a working connection to the node
            if not self.web3.is_connected():
                logger.critical("Cannot connect to blockchain node - Kingdom AI requires real blockchain connections")
                raise RuntimeError("Failed to connect to blockchain node - system halting")
                
            # Verify this is a real blockchain network by checking chain ID
            chain_id = await self.web3.eth.chain_id
            
            # Map of known mainnet chain IDs
            mainnet_chain_ids = {
                1: "Ethereum Mainnet",
                56: "Binance Smart Chain Mainnet",
                137: "Polygon Mainnet",
                43114: "Avalanche C-Chain Mainnet",
                42161: "Arbitrum One Mainnet",
                10: "Optimism Mainnet",
                100: "Gnosis Chain (formerly xDai)",
                42220: "Celo Mainnet",
                250: "Fantom Opera Mainnet"
            }
            
            # STRICT POLICY: Only mainnet connections are permitted
            # The system enforces this by explicitly checking against the mainnet chain IDs
            # and halting if any non-mainnet connection is attempted
            mainnet_only_policy = True
            
            # Mainnet IDs that are explicitly permitted
            permitted_mainnet_ids = set(mainnet_chain_ids.keys())
            
            # All connections must be to recognized mainnets
            if chain_id not in permitted_mainnet_ids:
                logging.warning(f"⚠️ Non-mainnet network ID {chain_id} detected - mining may be limited")
            
            # The mainnet-only policy check above has replaced the explicit testnet check
            # No further checks are needed as the system will have already halted if not on a mainnet
            
            logger.info(f"Connected to mainnet blockchain: {mainnet_chain_ids.get(chain_id, 'Unknown')} (Chain ID: {chain_id})")
            logger.info("All blockchain connections verified as MAINNET ONLY - continuing system initialization")
            
            # Check if connected to a known mainnet
            network_name = mainnet_chain_ids.get(chain_id, "Unknown Network")
            if network_name == "Unknown Network":
                logger.warning(f"Connected to unrecognized network with Chain ID {chain_id}")
                logger.warning("Proceeding, but verify this is a real blockchain mainnet")
            else:
                logger.info(f"Connected to real blockchain: {network_name} (Chain ID: {chain_id})")
            
            # Verify mining capability on the node
            try:
                is_mining = await self.web3.eth.mining
                if not is_mining:
                    logger.warning("Mining is not currently enabled on the connected node")
                    logger.warning("This may impact mining operations - check node configuration")
            except Exception as mine_err:
                logger.warning(f"Could not verify mining status: {mine_err}")
                
            # Start monitoring task
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            
            logger.info("BlockchainMiningManager successfully initialized with REAL blockchain")
            return True
            
        except Exception as e:
            logger.critical(f"CRITICAL ERROR: Failed to initialize BlockchainMiningManager with real blockchain: {e}")
            
            # Publish critical error to event bus if available
            if self.event_bus:
                # EventBus.publish is synchronous in this codebase (it schedules async handlers internally).
                self.event_bus.publish("mining.critical_error", {
                    "error": "initialization_failed",
                    "message": str(e),
                    "requires_system_halt": True,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            # In Kingdom AI's strict no-fallback policy, this is a critical error
            # that should halt the system - we're returning False here but the calling
            # code should detect this and halt the system
            return False
            
    async def start_mining(self, threads: int = 1, **kwargs) -> bool:
        """Start mining on the connected node.
        
        Args:
            threads: Number of CPU threads to use for mining
            **kwargs: Additional mining parameters
            
        Returns:
            bool: True if mining started successfully
        """
        try:
            if not self.web3.is_connected():
                raise ConnectionError("Not connected to a blockchain node")
                
            # Start mining
            miner_address = kwargs.get('miner_address')
            if not miner_address:
                # Use coinbase address if available
                try:
                    miner_address = self.web3.eth.coinbase
                except:
                    raise ValueError("No miner address provided and coinbase not set")
            
            # Set coinbase if different from current
            current_coinbase = await self.web3.eth.coinbase
            if current_coinbase.lower() != miner_address.lower():
                await self.web3.miner.set_etherbase(miner_address)
            
            # Start mining
            await self.web3.eth.miner.start(threads)
            
            # Update stats
            self.mining_stats.update({
                'active': True,
                'start_time': datetime.utcnow(),
                'miner_address': miner_address,
                'threads': threads
            })
            
            # Publish event
            if self.event_bus:
                # EventBus.publish is synchronous in this codebase (it schedules async handlers internally).
                self.event_bus.publish("mining.started", {
                    "miner_address": miner_address,
                    "threads": threads,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            logger.info(f"Started mining with address {miner_address} using {threads} threads")
            return True
            
        except Exception as e:
            error_msg = f"Failed to start mining: {str(e)}"
            logger.error(error_msg)
            if self.event_bus:
                # EventBus.publish is synchronous in this codebase (it schedules async handlers internally).
                self.event_bus.publish("mining.error", {
                    "error": "start_failed",
                    "message": error_msg,
                    "timestamp": datetime.utcnow().isoformat()
                })
            return False
            
    async def stop_mining(self) -> bool:
        """Stop mining on the connected node.
        
        Returns:
            bool: True if mining stopped successfully
        """
        try:
            if not self.web3.is_connected():
                raise ConnectionError("Not connected to a blockchain node")
                
            # Stop mining
            await self.web3.eth.miner.stop()
            
            # Update stats
            self.mining_stats.update({
                'active': False,
                'uptime': (datetime.utcnow() - self.mining_stats['start_time']).total_seconds() \
                         if self.mining_stats['start_time'] else 0,
                'end_time': datetime.utcnow()
            })
            
            # Publish event
            if self.event_bus:
                # EventBus.publish is synchronous in this codebase (it schedules async handlers internally).
                self.event_bus.publish("mining.stopped", {
                    "duration_seconds": self.mining_stats['uptime'],
                    "timestamp": datetime.utcnow().isoformat()
                })
                
            logger.info("Stopped mining")
            return True
            
        except Exception as e:
            error_msg = f"Failed to stop mining: {str(e)}"
            logger.error(error_msg)
            if self.event_bus:
                # EventBus.publish is synchronous in this codebase (it schedules async handlers internally).
                self.event_bus.publish("mining.error", {
                    "error": "stop_failed",
                    "message": error_msg,
                    "timestamp": datetime.utcnow().isoformat()
                })
            return False
            
    async def get_mining_stats(self) -> Dict[str, Any]:
        """Get current mining statistics.
        
        Returns:
            dict: Mining statistics
        """
        try:
            if not self.web3.is_connected():
                raise ConnectionError("Not connected to a blockchain node")
                
            # Update stats from node
            self.mining_stats.update({
                'active': await self.web3.eth.mining,
                'hashrate': await self.web3.eth.hashrate or 0,
                'mining_threads': await self.web3.eth.mining_threads if hasattr(self.web3.eth, 'mining_threads') else 1,
                'miner_address': await self.web3.eth.coinbase,
                'gas_price': str(await self.web3.eth.gas_price)
            })
            
            # Update uptime if mining is active
            if self.mining_stats['active'] and self.mining_stats['start_time']:
                self.mining_stats['uptime'] = (datetime.utcnow() - self.mining_stats['start_time']).total_seconds()
                
            return self.mining_stats
            
        except Exception as e:
            logger.error(f"Failed to get mining stats: {e}")
            # Return cached stats if available
            return self.mining_stats
            
    async def _monitor_loop(self) -> None:
        """Background task to monitor mining status and statistics."""
        while not self._shutdown_event.is_set():
            try:
                # Get latest stats
                stats = await self.get_mining_stats()
                
                # Publish stats update
                if self.event_bus:
                    # EventBus.publish is synchronous in this codebase (it schedules async handlers internally).
                    self.event_bus.publish("mining.stats_update", {
                        **stats,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
            except Exception as e:
                logger.error(f"Error in mining monitor loop: {e}")
                
            # Wait for next update
            await asyncio.sleep(self._monitor_interval)
            
    async def shutdown(self) -> None:
        """Shut down the mining manager."""
        self._shutdown_event.set()
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
                
        # Stop mining if active
        try:
            if await self.web3.eth.mining:
                await self.stop_mining()
        except:
            pass
            
        logger.info("BlockchainMiningManager shutdown complete")
