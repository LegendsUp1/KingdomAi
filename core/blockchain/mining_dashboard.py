"""Blockchain mining dashboard implementation for Kingdom AI."""

import logging
import asyncio
import json
import os
import time
import datetime
from typing import Dict, Any

# Setup logger
logger = logging.getLogger("kingdom_ai.blockchain.mining_dashboard")

# Import base component
from core.base_component import BaseComponent

# Constants
MINING_POOLS = {
    "bitcoin": [
        {"name": "Slush Pool", "url": "https://slushpool.com", "api_key": None},
        {"name": "F2Pool", "url": "https://f2pool.com", "api_key": None},
        {"name": "Antpool", "url": "https://antpool.com", "api_key": None},
        {"name": "Poolin", "url": "https://poolin.com", "api_key": None},
        {"name": "ViaBTC", "url": "https://viabtc.com", "api_key": None}
    ],
    "ethereum": [
        {"name": "Ethermine", "url": "https://ethermine.org", "api_key": None},
        {"name": "SparkPool", "url": "https://sparkpool.com", "api_key": None},
        {"name": "F2Pool", "url": "https://f2pool.com", "api_key": None},
        {"name": "Nanopool", "url": "https://nanopool.org", "api_key": None},
        {"name": "Hiveon", "url": "https://hiveon.net", "api_key": None}
    ]
}

MINING_HARDWARE = {
    "bitcoin": [
        {"name": "Antminer S19 Pro", "hashrate": 110, "power": 3250, "unit": "TH/s"},
        {"name": "Antminer S19", "hashrate": 95, "power": 3250, "unit": "TH/s"},
        {"name": "Whatsminer M30S++", "hashrate": 112, "power": 3472, "unit": "TH/s"},
        {"name": "Whatsminer M30S+", "hashrate": 100, "power": 3400, "unit": "TH/s"},
        {"name": "AvalonMiner 1246", "hashrate": 90, "power": 3420, "unit": "TH/s"}
    ],
    "ethereum": [
        {"name": "RTX 3090", "hashrate": 125, "power": 350, "unit": "MH/s"},
        {"name": "RTX 3080", "hashrate": 98, "power": 320, "unit": "MH/s"},
        {"name": "RTX 3070", "hashrate": 60, "power": 220, "unit": "MH/s"},
        {"name": "RTX 3060 Ti", "hashrate": 60, "power": 200, "unit": "MH/s"},
        {"name": "RX 6900 XT", "hashrate": 64, "power": 300, "unit": "MH/s"}
    ]
}


class MiningStats:
    """Mining statistics container."""
    
    def __init__(self, chain: str):
        """Initialize mining statistics.
        
        Args:
            chain: Blockchain name
        """
        self.chain = chain
        self.hashrate = 0
        self.unit = "H/s"
        self.workers_online = 0
        self.workers_total = 0
        self.revenue_24h = 0
        self.revenue_7d = 0
        self.revenue_30d = 0
        self.power_usage = 0
        self.power_cost_24h = 0
        self.efficiency = 0
        self.last_updated = time.time()
        self.mining_pool = None
        self.hardware = []
        self.history = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert mining stats to dictionary.
        
        Returns:
            Dictionary representation of mining stats
        """
        return {
            "chain": self.chain,
            "hashrate": self.hashrate,
            "unit": self.unit,
            "workers_online": self.workers_online,
            "workers_total": self.workers_total,
            "revenue_24h": self.revenue_24h,
            "revenue_7d": self.revenue_7d,
            "revenue_30d": self.revenue_30d,
            "power_usage": self.power_usage,
            "power_cost_24h": self.power_cost_24h,
            "efficiency": self.efficiency,
            "last_updated": self.last_updated,
            "mining_pool": self.mining_pool,
            "hardware": self.hardware,
            "history": self.history[:10]  # Limit to 10 most recent entries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MiningStats':
        """Create mining stats from dictionary.
        
        Args:
            data: Dictionary representation of mining stats
        
        Returns:
            MiningStats instance
        """
        stats = cls(data.get("chain", "unknown"))
        stats.hashrate = data.get("hashrate", 0)
        stats.unit = data.get("unit", "H/s")
        stats.workers_online = data.get("workers_online", 0)
        stats.workers_total = data.get("workers_total", 0)
        stats.revenue_24h = data.get("revenue_24h", 0)
        stats.revenue_7d = data.get("revenue_7d", 0)
        stats.revenue_30d = data.get("revenue_30d", 0)
        stats.power_usage = data.get("power_usage", 0)
        stats.power_cost_24h = data.get("power_cost_24h", 0)
        stats.efficiency = data.get("efficiency", 0)
        stats.last_updated = data.get("last_updated", time.time())
        stats.mining_pool = data.get("mining_pool")
        stats.hardware = data.get("hardware", [])
        stats.history = data.get("history", [])
        return stats


class MiningDashboard(BaseComponent):
    """Blockchain mining dashboard."""
    
    def __init__(self, event_bus=None, config=None):
        """Initialize mining dashboard.
        
        Args:
            event_bus: Event bus instance
            config: Configuration dictionary
        """
        super().__init__(name="MiningDashboard", event_bus=event_bus)
        self.config = config or {}
        self.stats = {}
        self.is_initialized = False
        self.is_monitoring = False
        self.monitor_task = None
        self.mining_pools = MINING_POOLS.copy()
        self.mining_hardware = MINING_HARDWARE.copy()
        self.power_cost_kwh = self.config.get("power_cost_kwh", 0.12)  # Default: $0.12/kWh
        self.update_interval = self.config.get("update_interval", 300)  # Default: 5 minutes
    
    async def initialize(self) -> bool:
        """Initialize mining dashboard.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            logger.info("Initializing mining dashboard")
            
            # Register event handlers
            if self.event_bus:
                self.event_bus.subscribe_sync("blockchain.mining.stats", self.handle_stats_request)
                self.event_bus.subscribe_sync("blockchain.mining.start", self.handle_start_mining)
                self.event_bus.subscribe_sync("blockchain.mining.stop", self.handle_stop_mining)
                self.event_bus.subscribe_sync("blockchain.mining.hardware", self.handle_hardware_request)
                self.event_bus.subscribe_sync("blockchain.mining.pools", self.handle_pools_request)
                self.event_bus.subscribe_sync("blockchain.mining.config", self.handle_config_update)
                self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
            
            # Create directory for mining data
            mining_dir = os.path.join("data", "mining")
            os.makedirs(mining_dir, exist_ok=True)
            
            # Load mining stats
            await self._load_stats()
            
            # Start monitoring
            await self.start_monitoring()
            
            logger.info("Mining dashboard initialized")
            self.is_initialized = True
            return True
        except Exception as e:
            logger.error(f"Error initializing mining dashboard: {e}")
            return False
    
    async def _load_stats(self) -> None:
        """Load mining stats from storage."""
        try:
            mining_dir = os.path.join("data", "mining")
            
            # Load stats for each blockchain
            for chain in ["bitcoin", "ethereum"]:
                stats_file = os.path.join(mining_dir, f"{chain}_stats.json")
                
                if os.path.exists(stats_file):
                    # Load stats from file
                    with open(stats_file, "r") as f:
                        stats_data = json.load(f)
                    
                    # Create stats object
                    self.stats[chain] = MiningStats.from_dict(stats_data)
                    logger.info(f"Loaded {chain} mining stats")
                else:
                    # Create new stats object
                    self.stats[chain] = MiningStats(chain)
                    logger.info(f"Created new {chain} mining stats")
                    
                    # Initialize with some hardware (simulated)
                    if chain in self.mining_hardware:
                        if len(self.mining_hardware[chain]) > 0:
                            # Add one of each hardware type
                            for hardware in self.mining_hardware[chain]:
                                self.stats[chain].hardware.append({
                                    "name": hardware["name"],
                                    "count": 1,
                                    "hashrate": hardware["hashrate"],
                                    "power": hardware["power"],
                                    "unit": hardware["unit"]
                                })
                    
                    # Initialize with a mining pool
                    if chain in self.mining_pools:
                        if len(self.mining_pools[chain]) > 0:
                            self.stats[chain].mining_pool = self.mining_pools[chain][0]["name"]
        except Exception as e:
            logger.error(f"Error loading mining stats: {e}")
    
    async def _save_stats(self) -> None:
        """Save mining stats to storage."""
        try:
            mining_dir = os.path.join("data", "mining")
            
            # Save stats for each blockchain
            for chain, stats in self.stats.items():
                stats_file = os.path.join(mining_dir, f"{chain}_stats.json")
                
                # Save stats to file
                with open(stats_file, "w") as f:
                    json.dump(stats.to_dict(), f, indent=2)
                
                logger.debug(f"Saved {chain} mining stats")
        except Exception as e:
            logger.error(f"Error saving mining stats: {e}")
    
    async def start_monitoring(self) -> bool:
        """Start mining monitoring.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.is_monitoring:
            logger.info("Mining monitoring already started")
            return True
        
        try:
            logger.info("Starting mining monitoring")
            
            # Create monitoring task
            self.monitor_task = asyncio.create_task(self._monitoring_loop())
            self.is_monitoring = True
            
            logger.info("Mining monitoring started")
            return True
        except Exception as e:
            logger.error(f"Error starting mining monitoring: {e}")
            return False
    
    async def stop_monitoring(self) -> bool:
        """Stop mining monitoring.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        if not self.is_monitoring:
            logger.info("Mining monitoring already stopped")
            return True
        
        try:
            logger.info("Stopping mining monitoring")
            
            # Cancel monitoring task
            if self.monitor_task:
                task = self.monitor_task
                self.monitor_task = None
                try:
                    task_loop = task.get_loop()
                except Exception:
                    task_loop = None
                try:
                    running_loop = asyncio.get_running_loop()
                except RuntimeError:
                    running_loop = None
                if task_loop is running_loop:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                else:
                    try:
                        task.cancel()
                    except Exception:
                        pass
            
            self.is_monitoring = False
            
            logger.info("Mining monitoring stopped")
            return True
        except Exception as e:
            logger.error(f"Error stopping mining monitoring: {e}")
            return False
    
    async def _monitoring_loop(self) -> None:
        """Mining monitoring loop."""
        try:
            while True:
                # Update mining stats
                await self._update_stats()
                
                # Save stats
                await self._save_stats()
                
                # Sleep until next update
                await asyncio.sleep(self.update_interval)
        except asyncio.CancelledError:
            logger.info("Mining monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in mining monitoring loop: {e}")
    
    async def _update_stats(self) -> None:
        """Update mining statistics."""
        logger.debug("Updating mining statistics")
        
        try:
            # Update stats for each blockchain
            for chain, stats in self.stats.items():
                # Calculate total hashrate and power usage
                total_hashrate = 0
                total_power = 0
                worker_count = 0
                
                for hardware in stats.hardware:
                    count = hardware.get("count", 1)
                    hashrate = hardware.get("hashrate", 0) * count
                    power = hardware.get("power", 0) * count
                    
                    total_hashrate += hashrate
                    total_power += power
                    worker_count += count
                
                # Store updated values
                stats.hashrate = total_hashrate
                stats.power_usage = total_power
                stats.workers_online = worker_count
                stats.workers_total = worker_count
                
                # Calculate power cost
                stats.power_cost_24h = (total_power / 1000) * 24 * self.power_cost_kwh
                
                # Calculate efficiency
                if total_power > 0:
                    stats.efficiency = total_hashrate / total_power
                else:
                    stats.efficiency = 0
                
                # Update revenue (simulated)
                # In a real implementation, this would query mining pool APIs
                # For now, we'll use simulated values
                if chain == "bitcoin":
                    # BTC mining rewards
                    stats.revenue_24h = total_hashrate * 0.0000001  # TH/s to BTC/day (simulated)
                    stats.revenue_7d = stats.revenue_24h * 7
                    stats.revenue_30d = stats.revenue_24h * 30
                elif chain == "ethereum":
                    # ETH mining rewards
                    stats.revenue_24h = total_hashrate * 0.0001  # MH/s to ETH/day (simulated)
                    stats.revenue_7d = stats.revenue_24h * 7
                    stats.revenue_30d = stats.revenue_24h * 30
                
                # Add history entry
                timestamp = time.time()
                history_entry = {
                    "timestamp": timestamp,
                    "datetime": datetime.datetime.fromtimestamp(timestamp).isoformat(),
                    "hashrate": stats.hashrate,
                    "workers_online": stats.workers_online,
                    "revenue_24h": stats.revenue_24h
                }
                
                stats.history.insert(0, history_entry)
                
                # Limit history size
                if len(stats.history) > 100:
                    stats.history = stats.history[:100]
                
                # Update last updated timestamp
                stats.last_updated = timestamp
                
                logger.debug(f"Updated {chain} mining stats: {total_hashrate} {stats.unit}, "
                             f"{worker_count} workers, {stats.revenue_24h:.8f} {chain}/day")
            
            # Publish stats update if event bus is available
            if self.event_bus:
                stats_dict = {chain: stats.to_dict() for chain, stats in self.stats.items()}
                self.event_bus.publish("blockchain.mining.stats.update", {
                    "stats": stats_dict,
                    "timestamp": time.time()
                })
                
        except Exception as e:
            logger.error(f"Error updating mining stats: {e}")
    
    async def handle_stats_request(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle mining stats request.
        
        Args:
            event_type: Event type
            data: Event data
        
        Returns:
            Response data
        """
        logger.info(f"Handling mining stats request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            
            if chain:
                # Request for specific blockchain
                if chain not in self.stats:
                    raise ValueError(f"No mining stats available for {chain}")
                
                # Get stats
                stats_dict = {chain: self.stats[chain].to_dict()}
            else:
                # Request for all blockchains
                stats_dict = {chain: stats.to_dict() for chain, stats in self.stats.items()}
            
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "stats": stats_dict,
                "timestamp": time.time()
            }
            
            # Publish response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.stats.response", response)
            
            return response
        except Exception as e:
            logger.error(f"Error handling mining stats request: {e}")
            
            # Build error response
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "message": f"Error getting mining stats: {str(e)}"
            }
            
            # Publish error response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.stats.error", response)
            
            return response
    
    async def handle_start_mining(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle start mining request.
        
        Args:
            event_type: Event type
            data: Event data
        
        Returns:
            Response data
        """
        logger.info(f"Handling start mining request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            
            if not chain:
                raise ValueError("chain is required")
            
            if chain not in self.stats:
                # Create stats for new chain
                self.stats[chain] = MiningStats(chain)
            
            # Start monitoring if not already started
            if not self.is_monitoring:
                try:
                    result = await self.start_monitoring()
                    if not result:
                        logger.warning("Failed to start monitoring, continuing anyway")
                except Exception as e:
                    logger.error(f"Error starting monitoring: {e}")
            
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "chain": chain,
                "message": f"Mining started for {chain}"
            }
            
            # Publish response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.start.response", response)
            
            return response
        except Exception as e:
            logger.error(f"Error handling start mining request: {e}")
            
            # Build error response
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "message": f"Error starting mining: {str(e)}"
            }
            
            # Publish error response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.start.error", response)
            
            return response
    
    async def handle_stop_mining(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle stop mining request.
        
        Args:
            event_type: Event type
            data: Event data
        
        Returns:
            Response data
        """
        logger.info(f"Handling stop mining request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            
            if not chain:
                raise ValueError("chain is required")
            
            if chain not in self.stats:
                raise ValueError(f"No mining stats available for {chain}")
            
            # Clear hardware list to simulate stopping
            self.stats[chain].hardware = []
            
            # Update stats
            await self._update_stats()
            
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "chain": chain,
                "message": f"Mining stopped for {chain}"
            }
            
            # Publish response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.stop.response", response)
            
            return response
        except Exception as e:
            logger.error(f"Error handling stop mining request: {e}")
            
            # Build error response
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "message": f"Error stopping mining: {str(e)}"
            }
            
            # Publish error response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.stop.error", response)
            
            return response
    
    async def handle_hardware_request(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle mining hardware request.
        
        Args:
            event_type: Event type
            data: Event data
        
        Returns:
            Response data
        """
        logger.info(f"Handling mining hardware request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            
            if chain:
                # Request for specific blockchain
                if chain not in self.mining_hardware:
                    raise ValueError(f"No mining hardware available for {chain}")
                
                # Get hardware list
                hardware_dict = {chain: self.mining_hardware[chain]}
            else:
                # Request for all blockchains
                hardware_dict = self.mining_hardware.copy()
            
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "hardware": hardware_dict
            }
            
            # Publish response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.hardware.response", response)
            
            return response
        except Exception as e:
            logger.error(f"Error handling mining hardware request: {e}")
            
            # Build error response
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "message": f"Error getting mining hardware: {str(e)}"
            }
            
            # Publish error response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.hardware.error", response)
            
            return response
    
    async def handle_pools_request(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle mining pools request.
        
        Args:
            event_type: Event type
            data: Event data
        
        Returns:
            Response data
        """
        logger.info(f"Handling mining pools request: {data}")
        
        try:
            # Extract parameters
            chain = data.get("chain")
            
            if chain:
                # Request for specific blockchain
                if chain not in self.mining_pools:
                    raise ValueError(f"No mining pools available for {chain}")
                
                # Get pools list
                pools_dict = {chain: self.mining_pools[chain]}
            else:
                # Request for all blockchains
                pools_dict = self.mining_pools.copy()
            
            # Build response
            response = {
                "request_id": data.get("request_id"),
                "status": "success",
                "pools": pools_dict
            }
            
            # Publish response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.pools.response", response)
            
            return response
        except Exception as e:
            logger.error(f"Error handling mining pools request: {e}")
            
            # Build error response
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "message": f"Error getting mining pools: {str(e)}"
            }
            
            # Publish error response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.pools.error", response)
            
            return response
    
    async def handle_config_update(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle mining configuration update.
        
        Args:
            event_type: Event type
            data: Event data
        
        Returns:
            Response data
        """
        logger.info(f"Handling mining configuration update: {data}")
        
        try:
            # Extract parameters
            config_type = data.get("type")
            
            if not config_type:
                raise ValueError("configuration type is required")
            
            if config_type == "hardware":
                # Add or update hardware
                chain = data.get("chain")
                hardware = data.get("hardware")
                
                if not chain or not hardware:
                    raise ValueError("chain and hardware are required")
                
                if chain not in self.stats:
                    self.stats[chain] = MiningStats(chain)
                
                # Check if hardware already exists
                found = False
                for i, existing in enumerate(self.stats[chain].hardware):
                    if existing["name"] == hardware["name"]:
                        # Update existing hardware
                        self.stats[chain].hardware[i] = hardware
                        found = True
                        break
                
                if not found:
                    # Add new hardware
                    self.stats[chain].hardware.append(hardware)
                
                # Update stats
                await self._update_stats()
                
                # Build response
                response = {
                    "request_id": data.get("request_id"),
                    "status": "success",
                    "type": config_type,
                    "chain": chain,
                    "message": f"Hardware updated for {chain}"
                }
            
            elif config_type == "pool":
                # Update mining pool
                chain = data.get("chain")
                pool = data.get("pool")
                
                if not chain or not pool:
                    raise ValueError("chain and pool are required")
                
                if chain not in self.stats:
                    self.stats[chain] = MiningStats(chain)
                
                # Update mining pool
                self.stats[chain].mining_pool = pool
                
                # Build response
                response = {
                    "request_id": data.get("request_id"),
                    "status": "success",
                    "type": config_type,
                    "chain": chain,
                    "message": f"Mining pool updated for {chain}"
                }
            
            elif config_type == "power_cost":
                # Update power cost
                power_cost = data.get("power_cost_kwh")
                
                if power_cost is None:
                    raise ValueError("power_cost_kwh is required")
                
                # Update power cost
                self.power_cost_kwh = float(power_cost)
                
                # Update stats
                await self._update_stats()
                
                # Build response
                response = {
                    "request_id": data.get("request_id"),
                    "status": "success",
                    "type": config_type,
                    "message": f"Power cost updated to ${self.power_cost_kwh}/kWh"
                }
            
            else:
                raise ValueError(f"Unsupported configuration type: {config_type}")
            
            # Save stats
            await self._save_stats()
            
            # Publish response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.config.response", response)
            
            return response
        except Exception as e:
            logger.error(f"Error handling mining configuration update: {e}")
            
            # Build error response
            response = {
                "request_id": data.get("request_id"),
                "status": "error",
                "message": f"Error updating mining configuration: {str(e)}"
            }
            
            # Publish error response
            if self.event_bus:
                self.event_bus.publish("blockchain.mining.config.error", response)
            
            return response
    
    async def handle_shutdown(self, data: Dict[str, Any]) -> None:
        """Handle system shutdown event.
        
        Args:
            data: Shutdown event data
        """
        logger.info("Handling mining dashboard shutdown")
        
        try:
            # Stop monitoring
            await self.stop_monitoring()
            
            # Save stats
            await self._save_stats()
            
            logger.info("Mining dashboard shutdown completed")
        except Exception as e:
            logger.error(f"Error during mining dashboard shutdown: {e}")
