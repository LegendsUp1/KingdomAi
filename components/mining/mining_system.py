#!/usr/bin/env python3
# Mining System for Kingdom AI
#
# This module handles all cryptocurrency mining operations with Redis integration
# and Qt-compatible event handling.


import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, Union

from core.base_component_v2 import BaseComponentV2
from core.redis_connector import RedisQuantumNexusConnector

# Configure logger
logger = logging.getLogger("KingdomAI.MiningSystem")

class MiningSystem(BaseComponentV2):
    """
    Mining System for Kingdom AI.
    
    This class manages all cryptocurrency mining operations with Redis integration
    and Qt-compatible event handling.
    """
    
    # Event types
    EVENT_MINER_STATUS = "mining.miner_status"
    EVENT_HASHRATE_UPDATE = "mining.hashrate_update"
    EVENT_TEMPERATURE_UPDATE = "mining.temperature_update"
    EVENT_POWER_UPDATE = "mining.power_update"
    EVENT_MINER_ERROR = "mining.error"
    
    def __init__(self, 
                 name: str = "MiningSystem",
                 event_bus: Optional[Any] = None,
                 config: Optional[Dict[str, Any]] = None):
        """Initialize the mining system.
        
        Args:
            name: Component name
            event_bus: Event bus for inter-component communication
            config: Configuration dictionary
        """
        super().__init__(name=name, event_bus=event_bus, config=config or {})
        
        # Initialize Redis connector
        self.redis = None
        
        # Mining state
        self.miners: Dict[str, Dict[str, Any]] = {}
        self.mining_pools: Dict[str, Dict[str, Any]] = {}
        self.mining_stats: Dict[str, Any] = {
            'total_hashrate': 0.0,
            'active_miners': 0,
            'total_power': 0.0,
            'total_profit': 0.0,
            'last_update': time.time()
        }
        
        # Mining parameters
        self.mining_enabled = False
        self.auto_switch = self.config.get('auto_switch', True)
        self.profit_threshold = float(self.config.get('profit_threshold', 0.0))
        
        # Initialize Redis keys
        self.redis_prefix = "kingdom:mining"
        
        # Monitoring task
        self._monitoring_task = None
        self._running = False
    
    async def _initialize(self) -> None:
        """Initialize the mining system."""
        self.logger.info("Initializing Mining System...")
        
        # Initialize Redis connection
        if not await self._init_redis():
            error_msg = "Failed to initialize Redis connection for Mining System"
            self.logger.critical(error_msg)
            await self._shutdown_on_redis_failure()
            return
        
        # Load initial state from Redis if available
        await self._load_state()
        
        # Register event handlers
        await self._register_event_handlers()
        
        # Start monitoring loop
        self._start_monitoring_loop()
        
        self.logger.info("Mining System initialized")
    
    async def _start(self) -> None:
        """Start the mining system."""
        self.logger.info("Starting Mining System...")
        self._running = True
        
        # Start monitoring mining hardware
        await self._start_mining_hardware_monitoring()
        
        # Connect to mining pools
        await self._connect_to_mining_pools()
        
        # Publish system started event
        await self.publish_event("mining.system_started", {
            'timestamp': time.time(),
            'miners': len(self.miners),
            'pools': len(self.mining_pools)
        })
        
        self.logger.info("Mining System started")
    
    async def _stop(self) -> None:
        """Stop the mining system."""
        self.logger.info("Stopping Mining System...")
        self._running = False
        
        # Stop all mining operations
        await self.stop_mining()
        
        # Disconnect from mining pools
        await self._disconnect_from_mining_pools()
        
        # Save state to Redis
        await self._save_state()
        
        # Clean up Redis connection
        await self._cleanup_redis()
        
        # Publish system stopped event
        await self.publish_event("mining.system_stopped", {
            'timestamp': time.time()
        })
        
        self.logger.info("Mining System stopped")
    
    async def _register_event_handlers(self) -> None:
        """Register event handlers."""
        await super()._register_event_handlers()
        
        # System events
        await self.subscribe(f"{self.EVENT_SYSTEM}.shutdown", self._on_system_shutdown)
        
        # Mining control events
        await self.subscribe("mining.start", self._on_start_mining)
        await self.subscribe("mining.stop", self._on_stop_mining)
        await self.subscribe("mining.status_request", self._on_status_request)
        
        # Miner control events
        await self.subscribe("mining.miner.start", self._on_start_miner)
        await self.subscribe("mining.miner.stop", self._on_stop_miner)
        await self.subscribe("mining.miner.restart", self._on_restart_miner)
        await self.subscribe("mining.miner.update_config", self._on_update_miner_config)
        
        # Pool control events
        await self.subscribe("mining.pool.add", self._on_add_pool)
        await self.subscribe("mining.pool.remove", self._on_remove_pool)
        await self.subscribe("mining.pool.switch", self._on_switch_pool)
    
    async def _init_redis(self) -> bool:
        """Initialize Redis connection."""
        try:
            self.redis = RedisQuantumNexusConnector(
                name=f"{self.name}_redis",
                event_bus=self.event_bus,
                config={
                    'host': '127.0.0.1',
                    'port': 6380,
                    'password': 'QuantumNexus2025',
                    'db': 0,
                    'socket_timeout': 5,
                    'socket_connect_timeout': 5,
                    'retry_on_timeout': True,
                    'health_check_interval': 30,
                    'decode_responses': True
                }
            )
            
            # Initialize the Redis connection
            if not await self.redis.initialize():
                raise ConnectionError("Failed to initialize Redis connector")
            
            # Test connection
            if not await self.redis.ping():
                raise ConnectionError("Redis health check failed")
            
            self.logger.info("Redis connection established successfully")
            return True
            
        except Exception as e:
            self._handle_error("Failed to connect to Redis", e)
            return False
    
    async def _load_state(self) -> None:
        """Load mining state from Redis."""
        if not self.redis:
            self.logger.warning("Cannot load state: Redis not connected")
            return
        
        try:
            # Load miners
            miners_key = f"{self.redis_prefix}:miners"
            miners_data = await self.redis.get(miners_key)
            if miners_data:
                self.miners = json.loads(miners_data)
                self.logger.info(f"Loaded {len(self.miners)} miners from Redis")
            
            # Load mining pools
            pools_key = f"{self.redis_prefix}:pools"
            pools_data = await self.redis.get(pools_key)
            if pools_data:
                self.mining_pools = json.loads(pools_data)
                self.logger.info(f"Loaded {len(self.mining_pools)} mining pools from Redis")
            
            # Load mining stats
            stats_key = f"{self.redis_prefix}:stats"
            stats_data = await self.redis.get(stats_key)
            if stats_data:
                self.mining_stats = json.loads(stats_data)
                self.logger.info("Loaded mining stats from Redis")
                
        except Exception as e:
            self._handle_error("Failed to load state from Redis", e)
    
    async def _save_state(self) -> None:
        """Save mining state to Redis."""
        if not self.redis:
            self.logger.warning("Cannot save state: Redis not connected")
            return
        
        try:
            # Save miners
            miners_key = f"{self.redis_prefix}:miners"
            await self.redis.set(miners_key, json.dumps(self.miners))
            
            # Save mining pools
            pools_key = f"{self.redis_prefix}:pools"
            await self.redis.set(pools_key, json.dumps(self.mining_pools))
            
            # Save mining stats
            stats_key = f"{self.redis_prefix}:stats"
            await self.redis.set(stats_key, json.dumps(self.mining_stats))
            
            self.logger.debug("Mining state saved to Redis")
            
        except Exception as e:
            self._handle_error("Failed to save state to Redis", e)
    
    def _start_monitoring_loop(self) -> None:
        """Start the monitoring loop for mining hardware."""
        async def monitoring_loop():
            while self._running:
                try:
                    # Update miner status
                    await self._update_miner_status()
                    
                    # Update mining stats
                    await self._update_mining_stats()
                    
                    # Check for profitability and auto-switch if enabled
                    if self.auto_switch:
                        await self._check_profitability()
                    
                    # Small delay to prevent tight loop
                    await asyncio.sleep(5)  # Update every 5 seconds
                    
                except Exception as e:
                    self._handle_error("Error in monitoring loop", e)
                    await asyncio.sleep(5)  # Prevent tight loop on errors
        
        # Start the monitoring loop
        self._monitoring_task = asyncio.create_task(monitoring_loop())
    
    async def _update_miner_status(self) -> None:
        """Update status of all miners."""
        # This would query each miner for its current status
        # and update the internal state
        
        # Example implementation (would be replaced with actual hardware communication)
        for miner_id, miner in self.miners.items():
            try:
                # Simulate getting status from miner
                status = {
                    'status': 'mining' if self.mining_enabled else 'idle',
                    'hashrate': 100.0,  # MH/s
                    'accepted_shares': 0,
                    'rejected_shares': 0,
                    'temperature': 65.0,  # °C
                    'power': 200.0,  # W
                    'uptime': 3600,  # seconds
                    'last_update': time.time()
                }
                
                # Update miner status
                miner['status'] = status
                
                # Publish status update
                await self.publish_event(
                    self.EVENT_MINER_STATUS,
                    {
                        'miner_id': miner_id,
                        'status': status
                    }
                )
                
                # Publish hashrate update
                await self.publish_event(
                    self.EVENT_HASHRATE_UPDATE,
                    {
                        'miner_id': miner_id,
                        'hashrate': status['hashrate'],
                        'timestamp': time.time()
                    }
                )
                
                # Publish temperature update
                await self.publish_event(
                    self.EVENT_TEMPERATURE_UPDATE,
                    {
                        'miner_id': miner_id,
                        'temperature': status['temperature'],
                        'timestamp': time.time()
                    }
                )
                
                # Publish power update
                await self.publish_event(
                    self.EVENT_POWER_UPDATE,
                    {
                        'miner_id': miner_id,
                        'power': status['power'],
                        'timestamp': time.time()
                    }
                )
                
            except Exception as e:
                self._handle_error(f"Failed to update status for miner {miner_id}", e)
    
    async def _update_mining_stats(self) -> None:
        """Update mining statistics."""
        try:
            # Calculate total hashrate
            total_hashrate = sum(
                miner['status']['hashrate'] 
                for miner in self.miners.values() 
                if 'status' in miner and 'hashrate' in miner['status']
            )
            
            # Calculate total power
            total_power = sum(
                miner['status']['power'] 
                for miner in self.miners.values() 
                if 'status' in miner and 'power' in miner['status']
            )
            
            # Update stats
            self.mining_stats.update({
                'total_hashrate': total_hashrate,
                'total_power': total_power,
                'active_miners': len([m for m in self.miners.values() if m.get('status', {}).get('status') == 'mining']),
                'last_update': time.time()
            })
            
            # Publish stats update
            await self.publish_event(
                "mining.stats_update",
                self.mining_stats
            )
            
        except Exception as e:
            self._handle_error("Failed to update mining stats", e)
    
    async def _check_profitability(self) -> None:
        """Check mining profitability and switch pools if needed."""
        if not self.auto_switch or not self.mining_pools:
            return
        
        try:
            # Find the most profitable pool
            most_profitable = None
            max_profit = 0.0
            
            for pool_id, pool in self.mining_pools.items():
                pool_hashrate = pool.get('hashrate', 0)
                pool_reward_rate = pool.get('reward_rate', 0)
                coin_price = pool.get('coin_price', 0)
                pool_fee = pool.get('fee', 0.01)
                power_cost_per_hour = self.mining_stats.get('total_power', 0) * pool.get('electricity_rate', 0.10) / 1000

                gross_revenue = pool_hashrate * pool_reward_rate * coin_price * (1 - pool_fee)
                profit = gross_revenue - power_cost_per_hour

                if profit > max_profit:
                    max_profit = profit
                    most_profitable = pool_id
            
            # If current pool is not the most profitable, switch
            current_pool = next((p for p in self.mining_pools.values() if p.get('active', False)), None)
            if current_pool and most_profitable != current_pool['id'] and max_profit > self.profit_threshold:
                await self.switch_pool(most_profitable)
                
        except Exception as e:
            self._handle_error("Error checking profitability", e)
    
    # ===== Event Handlers =====
    
    async def _on_system_shutdown(self, event: dict) -> None:
        """Handle system shutdown event."""
        self.logger.info("Received system shutdown event")
        await self.stop()
    
    async def _on_start_mining(self, event: dict) -> None:
        """Handle start mining event."""
        self.logger.info("Received start mining event")
        await self.start_mining()
    
    async def _on_stop_mining(self, event: dict) -> None:
        """Handle stop mining event."""
        self.logger.info("Received stop mining event")
        await self.stop_mining()
    
    async def _on_status_request(self, event: dict) -> None:
        """Handle status request event."""
        self.logger.debug("Received status request event")
        await self.publish_event(
            "mining.status_response",
            {
                'mining_enabled': self.mining_enabled,
                'miners': {k: v['status'] for k, v in self.miners.items() if 'status' in v},
                'active_pool': next((p for p in self.mining_pools.values() if p.get('active', False)), None),
                'stats': self.mining_stats
            }
        )
    
    async def _on_start_miner(self, event: dict) -> None:
        """Handle start miner event."""
        miner_id = event.get('miner_id')
        if not miner_id:
            self.logger.error("No miner_id provided in start_miner event")
            return
            
        self.logger.info(f"Starting miner: {miner_id}")
        await self.start_miner(miner_id)
    
    async def _on_stop_miner(self, event: dict) -> None:
        """Handle stop miner event."""
        miner_id = event.get('miner_id')
        if not miner_id:
            self.logger.error("No miner_id provided in stop_miner event")
            return
            
        self.logger.info(f"Stopping miner: {miner_id}")
        await self.stop_miner(miner_id)
    
    async def _on_restart_miner(self, event: dict) -> None:
        """Handle restart miner event."""
        miner_id = event.get('miner_id')
        if not miner_id:
            self.logger.error("No miner_id provided in restart_miner event")
            return
            
        self.logger.info(f"Restarting miner: {miner_id}")
        await self.restart_miner(miner_id)
    
    async def _on_update_miner_config(self, event: dict) -> None:
        """Handle update miner config event."""
        miner_id = event.get('miner_id')
        config = event.get('config', {})
        
        if not miner_id or not config:
            self.logger.error("Invalid miner config update event")
            return
            
        self.logger.info(f"Updating config for miner: {miner_id}")
        await self.update_miner_config(miner_id, config)
    
    async def _on_add_pool(self, event: dict) -> None:
        """Handle add pool event."""
        pool_config = event.get('pool_config')
        if not pool_config:
            self.logger.error("No pool_config provided in add_pool event")
            return
            
        self.logger.info(f"Adding new mining pool: {pool_config.get('url')}")
        await self.add_mining_pool(pool_config)
    
    async def _on_remove_pool(self, event: dict) -> None:
        """Handle remove pool event."""
        pool_id = event.get('pool_id')
        if not pool_id:
            self.logger.error("No pool_id provided in remove_pool event")
            return
            
        self.logger.info(f"Removing mining pool: {pool_id}")
        await self.remove_mining_pool(pool_id)
    
    async def _on_switch_pool(self, event: dict) -> None:
        """Handle switch pool event."""
        pool_id = event.get('pool_id')
        if not pool_id:
            self.logger.error("No pool_id provided in switch_pool event")
            return
            
        self.logger.info(f"Switching to mining pool: {pool_id}")
        await self.switch_pool(pool_id)
    
    # ===== Public API Methods =====
    
    async def start_mining(self) -> bool:
        """Start the mining operation."""
        if self.mining_enabled:
            self.logger.warning("Mining is already running")
            return True
            
        try:
            self.logger.info("Starting mining operation")
            
            # Start all miners
            success = True
            for miner_id in self.miners:
                if not await self.start_miner(miner_id):
                    success = False
                    
            if not success:
                self.logger.error("Failed to start one or more miners")
                return False
                
            self.mining_enabled = True
            await self.publish_event("mining.started", {'timestamp': time.time()})
            self.logger.info("Mining operation started successfully")
            return True
            
        except Exception as e:
            self._handle_error("Failed to start mining", e)
            return False
    
    async def stop_mining(self) -> bool:
        """Stop the mining operation."""
        if not self.mining_enabled:
            self.logger.warning("Mining is not running")
            return True
            
        try:
            self.logger.info("Stopping mining operation")
            
            # Stop all miners
            success = True
            for miner_id in self.miners:
                if not await self.stop_miner(miner_id):
                    success = False
                    
            if not success:
                self.logger.error("Failed to stop one or more miners")
                return False
                
            self.mining_enabled = False
            await self.publish_event("mining.stopped", {'timestamp': time.time()})
            self.logger.info("Mining operation stopped successfully")
            return True
            
        except Exception as e:
            self._handle_error("Failed to stop mining", e)
            return False
    
    async def start_miner(self, miner_id: str) -> bool:
        """Start a specific miner."""
        if miner_id not in self.miners:
            self.logger.error(f"Miner not found: {miner_id}")
            return False
            
        try:
            miner = self.miners[miner_id]
            
            # Skip if already running
            if miner.get('status', {}).get('status') == 'mining':
                self.logger.warning(f"Miner {miner_id} is already running")
                return True
                
            self.logger.info(f"Starting miner: {miner_id}")

            if 'status' not in miner:
                miner['status'] = {}
            miner['status'].update({
                'status': 'starting',
                'start_time': time.time()
            })

            algo = miner.get('algorithm', 'sha256')
            pool = miner.get('pool', {})
            pool_url = pool.get('url', '')
            worker = pool.get('worker', miner_id)
            if pool_url and hasattr(self, '_connect_stratum'):
                await self._connect_stratum(miner_id, pool_url, worker, algo)
            else:
                await asyncio.sleep(0.5)
            
            # Update status
            miner['status'].update({
                'status': 'mining',
                'last_update': time.time(),
                'hashrate': 0.0,
                'accepted_shares': 0,
                'rejected_shares': 0,
                'temperature': 0.0,
                'power': 0.0,
                'uptime': 0
            })
            
            # Publish status update
            await self.publish_event(
                self.EVENT_MINER_STATUS,
                {
                    'miner_id': miner_id,
                    'status': miner['status']
                }
            )
            
            self.logger.info(f"Miner {miner_id} started successfully")
            return True
            
        except Exception as e:
            self._handle_error(f"Failed to start miner {miner_id}", e)
            return False
    
    async def stop_miner(self, miner_id: str) -> bool:
        """Stop a specific miner."""
        if miner_id not in self.miners:
            self.logger.error(f"Miner not found: {miner_id}")
            return False
            
        try:
            miner = self.miners[miner_id]
            
            # Skip if already stopped
            if miner.get('status', {}).get('status') != 'mining':
                self.logger.warning(f"Miner {miner_id} is not running")
                return True
                
            self.logger.info(f"Stopping miner: {miner_id}")
            if hasattr(self, '_stratum_connections') and miner_id in self._stratum_connections:
                conn = self._stratum_connections.pop(miner_id, None)
                if conn and hasattr(conn, 'close'):
                    try:
                        conn.close()
                    except Exception:
                        pass
            
            # Update status
            miner['status'].update({
                'status': 'stopping',
                'last_update': time.time()
            })
            
            # Simulate miner stop (replace with actual implementation)
            await asyncio.sleep(1)
            
            # Update status
            miner['status'].update({
                'status': 'stopped',
                'last_update': time.time(),
                'hashrate': 0.0,
                'temperature': 0.0,
                'power': 0.0
            })
            
            # Publish status update
            await self.publish_event(
                self.EVENT_MINER_STATUS,
                {
                    'miner_id': miner_id,
                    'status': miner['status']
                }
            )
            
            self.logger.info(f"Miner {miner_id} stopped successfully")
            return True
            
        except Exception as e:
            self._handle_error(f"Failed to stop miner {miner_id}", e)
            return False
    
    async def restart_miner(self, miner_id: str) -> bool:
        """Restart a specific miner."""
        if miner_id not in self.miners:
            self.logger.error(f"Miner not found: {miner_id}")
            return False
            
        try:
            # Stop the miner if it's running
            if self.miners[miner_id].get('status', {}).get('status') == 'mining':
                if not await self.stop_miner(miner_id):
                    return False
                
                # Small delay before restarting
                await asyncio.sleep(1)
            
            # Start the miner
            return await self.start_miner(miner_id)
            
        except Exception as e:
            self._handle_error(f"Failed to restart miner {miner_id}", e)
            return False
    
    async def update_miner_config(self, miner_id: str, config: dict) -> bool:
        """Update configuration for a specific miner."""
        if miner_id not in self.miners:
            self.logger.error(f"Miner not found: {miner_id}")
            return False
            
        try:
            miner = self.miners[miner_id]
            
            # Update miner configuration
            miner['config'].update(config)
            
            # If the miner is running, restart it to apply new config
            if miner.get('status', {}).get('status') == 'mining':
                self.logger.info(f"Restarting miner {miner_id} to apply new configuration")
                return await self.restart_miner(miner_id)
                
            return True
            
        except Exception as e:
            self._handle_error(f"Failed to update config for miner {miner_id}", e)
            return False
    
    async def add_mining_pool(self, pool_config: dict) -> bool:
        """Add a new mining pool."""
        try:
            # Validate pool config
            required_fields = ['id', 'url', 'user', 'password', 'algorithm']
            for field in required_fields:
                if field not in pool_config:
                    raise ValueError(f"Missing required field: {field}")
            
            pool_id = pool_config['id']
            
            # Check if pool already exists
            if pool_id in self.mining_pools:
                self.logger.warning(f"Pool {pool_id} already exists")
                return False
            
            # Add the pool
            self.mining_pools[pool_id] = {
                'id': pool_id,
                'url': pool_config['url'],
                'user': pool_config['user'],
                'password': pool_config['password'],
                'algorithm': pool_config['algorithm'],
                'enabled': True,
                'priority': len(self.mining_pools) + 1,
                'added_at': time.time(),
                'stats': {
                    'shares_accepted': 0,
                    'shares_rejected': 0,
                    'avg_hashrate': 0.0,
                    'last_share_time': 0
                }
            }
            
            # If this is the first pool, make it active
            if len(self.mining_pools) == 1:
                self.mining_pools[pool_id]['active'] = True
            else:
                self.mining_pools[pool_id]['active'] = False
            
            # Save state
            await self._save_state()
            
            # Publish event
            await self.publish_event(
                "mining.pool_added",
                {
                    'pool_id': pool_id,
                    'pool': self.mining_pools[pool_id]
                }
            )
            
            self.logger.info(f"Added new mining pool: {pool_id}")
            return True
            
        except Exception as e:
            self._handle_error("Failed to add mining pool", e)
            return False
    
    async def remove_mining_pool(self, pool_id: str) -> bool:
        """Remove a mining pool."""
        if pool_id not in self.mining_pools:
            self.logger.error(f"Pool not found: {pool_id}")
            return False
            
        try:
            # Don't remove the active pool
            if self.mining_pools[pool_id].get('active', False):
                self.logger.error(f"Cannot remove active pool: {pool_id}")
                return False
                
            # Remove the pool
            del self.mining_pools[pool_id]
            
            # Save state
            await self._save_state()
            
            # Publish event
            await self.publish_event(
                "mining.pool_removed",
                {'pool_id': pool_id}
            )
            
            self.logger.info(f"Removed mining pool: {pool_id}")
            return True
            
        except Exception as e:
            self._handle_error(f"Failed to remove mining pool {pool_id}", e)
            return False
    
    async def switch_pool(self, pool_id: str) -> bool:
        """Switch to a different mining pool."""
        if pool_id not in self.mining_pools:
            self.logger.error(f"Pool not found: {pool_id}")
            return False
            
        try:
            # Skip if already active
            if self.mining_pools[pool_id].get('active', False):
                self.logger.warning(f"Pool {pool_id} is already active")
                return True
                
            # Get current active pool
            current_pool = next(
                (p for p in self.mining_pools.values() if p.get('active', False)),
                None
            )
            
            # Switch to the new pool
            if current_pool:
                current_pool['active'] = False
                
            self.mining_pools[pool_id]['active'] = True
            
            # Save state
            await self._save_state()
            
            # Publish event
            await self.publish_event(
                "mining.pool_switched",
                {
                    'old_pool_id': current_pool['id'] if current_pool else None,
                    'new_pool_id': pool_id
                }
            )
            
            self.logger.info(f"Switched to mining pool: {pool_id}")
            
            # If mining is active, restart to apply new pool
            if self.mining_enabled:
                self.logger.info("Restarting mining to apply new pool")
                await self.stop_mining()
                await asyncio.sleep(1)
                await self.start_mining()
            
            return True
            
        except Exception as e:
            self._handle_error(f"Failed to switch to pool {pool_id}", e)
            return False
            
    # ===== Utility Methods =====
    
    def get_active_pool(self) -> Optional[dict]:
        """Get the currently active mining pool."""
        return next(
            (p for p in self.mining_pools.values() if p.get('active', False)),
            None
        )
    
    def get_miner(self, miner_id: str) -> Optional[dict]:
        """Get miner by ID."""
        return self.miners.get(miner_id)
    
    def get_miners(self) -> Dict[str, dict]:
        """Get all miners."""
        return self.miners
    
    def get_pool(self, pool_id: str) -> Optional[dict]:
        """Get pool by ID."""
        return self.mining_pools.get(pool_id)
    
    def get_pools(self) -> Dict[str, dict]:
        """Get all mining pools."""
        return self.mining_pools
    
    def get_stats(self) -> dict:
        """Get mining statistics."""
        return self.mining_stats
    
    def is_mining(self) -> bool:
        """Check if mining is currently active."""
        return self.mining_enabled
    
    def get_total_hashrate(self) -> float:
        """Get total hashrate across all miners."""
        return sum(
            m.get('status', {}).get('hashrate', 0.0)
            for m in self.miners.values()
            if m.get('status', {}).get('status') == 'mining'
        )
    
    def get_total_power(self) -> float:
        """Get total power consumption across all miners."""
        return sum(
            m.get('status', {}).get('power', 0.0)
            for m in self.miners.values()
            if m.get('status', {}).get('status') == 'mining'
        )
    
    def get_total_shares(self) -> dict:
        """Get total accepted and rejected shares."""
        accepted = sum(
            m.get('status', {}).get('accepted_shares', 0)
            for m in self.miners.values()
        )
        rejected = sum(
            m.get('status', {}).get('rejected_shares', 0)
            for m in self.miners.values()
        )
        return {'accepted': accepted, 'rejected': rejected}
    
    async def update_pool_stats(self, pool_id: str, stats: dict) -> bool:
        """Update statistics for a mining pool."""
        if pool_id not in self.mining_pools:
            self.logger.error(f"Pool not found: {pool_id}")
            return False
            
        try:
            # Update pool stats
            self.mining_pools[pool_id]['stats'].update(stats)
            self.mining_pools[pool_id]['last_update'] = time.time()
            
            # Publish stats update
            await self.publish_event(
                "mining.pool_stats_updated",
                {
                    'pool_id': pool_id,
                    'stats': self.mining_pools[pool_id]['stats']
                }
            )
            
            return True
            
        except Exception as e:
            self._handle_error(f"Failed to update stats for pool {pool_id}", e)
            return False
    
    async def update_miner_stats(self, miner_id: str, stats: dict) -> bool:
        """Update statistics for a miner."""
        if miner_id not in self.miners:
            self.logger.error(f"Miner not found: {miner_id}")
            return False
            
        try:
            # Update miner stats
            if 'status' not in self.miners[miner_id]:
                self.miners[miner_id]['status'] = {}
                
            self.miners[miner_id]['status'].update(stats)
            self.miners[miner_id]['status']['last_update'] = time.time()
            
            # Update global stats
            await self._update_global_stats()
            
            # Publish stats update
            await self.publish_event(
                self.EVENT_MINER_STATUS,
                {
                    'miner_id': miner_id,
                    'status': self.miners[miner_id]['status']
                }
            )
            
            return True
            
        except Exception as e:
            self._handle_error(f"Failed to update stats for miner {miner_id}", e)
            return False
    
    async def _update_global_stats(self) -> None:
        """Update global mining statistics."""
        try:
            total_hashrate = 0.0
            total_power = 0.0
            active_miners = 0
            total_shares = 0
            
            # Calculate totals
            for miner in self.miners.values():
                if miner.get('status', {}).get('status') == 'mining':
                    active_miners += 1
                    total_hashrate += miner.get('status', {}).get('hashrate', 0.0)
                    total_power += miner.get('status', {}).get('power', 0.0)
                    total_shares += miner.get('status', {}).get('accepted_shares', 0)
            
            # Update stats
            self.mining_stats.update({
                'total_hashrate': total_hashrate,
                'total_power': total_power,
                'active_miners': active_miners,
                'total_shares': total_shares,
                'last_update': time.time()
            })
            
            # Publish stats update
            await self.publish_event("mining.stats_updated", self.mining_stats)
            
        except Exception as e:
            self._handle_error("Failed to update global stats", e)
    
    async def reset_stats(self) -> None:
        """Reset all mining statistics."""
        try:
            # Reset miner stats
            for miner in self.miners.values():
                if 'status' in miner:
                    miner['status'].update({
                        'hashrate': 0.0,
                        'accepted_shares': 0,
                        'rejected_shares': 0,
                        'last_share_time': 0,
                        'uptime': 0
                    })
            
            # Reset pool stats
            for pool in self.mining_pools.values():
                pool['stats'].update({
                    'shares_accepted': 0,
                    'shares_rejected': 0,
                    'avg_hashrate': 0.0,
                    'last_share_time': 0
                })
            
            # Reset global stats
            self.mining_stats = {
                'start_time': time.time(),
                'total_hashrate': 0.0,
                'total_power': 0.0,
                'active_miners': 0,
                'total_shares': 0,
                'last_update': time.time()
            }
            
            # Save state
            await self._save_state()
            
            # Publish reset event
            await self.publish_event("mining.stats_reset", {'timestamp': time.time()})
            
            self.logger.info("Mining statistics reset")
            
        except Exception as e:
            self._handle_error("Failed to reset mining statistics", e)
    
    async def get_mining_summary(self) -> dict:
        """Get a summary of the mining operation."""
        active_pool = self.get_active_pool()
        
        return {
            'mining_enabled': self.mining_enabled,
            'active_miners': sum(1 for m in self.miners.values() if m.get('status', {}).get('status') == 'mining'),
            'total_miners': len(self.miners),
            'active_pool': active_pool['url'] if active_pool else None,
            'total_pools': len(self.mining_pools),
            'total_hashrate': self.get_total_hashrate(),
            'total_power': self.get_total_power(),
            'shares': self.get_total_shares(),
            'uptime': time.time() - (self.mining_stats.get('start_time', time.time())),
            'last_update': self.mining_stats.get('last_update', 0)
        }
