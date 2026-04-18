"""
Advanced Mining Manager for Kingdom AI
Integrates all mining capabilities: CPU, GPU, Bitcoin, Kaspa, Dual Mining
Provides unified interface for the mining system
"""

import logging
import asyncio
import threading
from typing import Dict, Optional, Any, List
from enum import Enum

from core.mining.hashrate_tracker import HashrateTracker, GlobalHashrateTracker
from core.mining.bitcoin_miner import RealBTCMiner, measure_hashrate
from core.mining.gpu_miners import LolMinerGPU, OpenCLBitcoinMiner, DualMiner

logger = logging.getLogger("KingdomAI.AdvancedMiningManager")


class MiningMode(Enum):
    """Mining mode enumeration"""
    STOPPED = "stopped"
    CPU_BITCOIN = "cpu_bitcoin"
    GPU_KASPA = "gpu_kaspa"
    GPU_BITCOIN = "gpu_bitcoin"
    DUAL = "dual"  # BTC CPU + Kaspa GPU
    

class AdvancedMiningManager:
    """Unified manager for all mining operations"""
    
    def __init__(self, event_bus=None):
        """Initialize advanced mining manager
        
        Args:
            event_bus: Event bus for publishing mining events
        """
        self.event_bus = event_bus
        self.mode = MiningMode.STOPPED
        self.tracker = GlobalHashrateTracker.get_instance()
        
        # Miners
        self.btc_miner: Optional[RealBTCMiner] = None
        self.kas_miner: Optional[LolMinerGPU] = None
        self.dual_miner: Optional[DualMiner] = None
        self.quantum_miner = None  # Quantum-GPU Bitcoin miner
        
        # Configuration - load from multi_coin_wallets.json
        self.config = {
            'btc_address': None,
            'kas_wallet': None,
            'btc_pool': 'btc.viabtc.com:3333',
            'kas_pool': 'kas.2miners.com:2020',
            'num_workers': None  # Auto-detect
        }
        
        # Load wallet addresses from config
        try:
            import json
            from pathlib import Path
            config_path = Path(__file__).parent.parent.parent / 'config' / 'multi_coin_wallets.json'
            if config_path.exists():
                with open(config_path, 'r') as f:
                    wallet_config = json.load(f)
                    self.config['btc_address'] = wallet_config.get('gpu_wallets', {}).get('BTC')
                    self.config['kas_wallet'] = wallet_config.get('gpu_wallets', {}).get('KAS')
                    if self.config['btc_address']:
                        logger.info(f"✅ Loaded Bitcoin address from config: {self.config['btc_address'][:10]}...")
                    if self.config['kas_wallet']:
                        logger.info(f"✅ Loaded Kaspa wallet from config: {self.config['kas_wallet'][:10]}...")
        except Exception as e:
            logger.debug(f"Could not load wallet config: {e}")
        
        # Stats update thread
        self.stats_thread: Optional[threading.Thread] = None
        self.stats_running = False
        
        logger.info("Advanced Mining Manager initialized")
        
        # SOTA 2026: Register on EventBus for component discovery
        if self.event_bus:
            try:
                from core.component_registry import register_component
                register_component('mining_system', self)
                logger.info("✅ Mining system registered on EventBus")
            except Exception as e:
                logger.debug(f"Component registration failed: {e}")
        
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize with configuration
        
        Args:
            config: Configuration dictionary
            
        Returns:
            bool: True if successful
        """
        try:
            self.config.update(config)
            
            # Validate addresses
            if not self.config.get('btc_address'):
                logger.warning("No Bitcoin address configured")
            if not self.config.get('kas_wallet'):
                logger.warning("No Kaspa wallet configured")
                
            logger.info("Advanced Mining Manager configured")
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
            
    async def start_mining(self, mode: str, **kwargs) -> bool:
        """Start mining in specified mode
        
        Args:
            mode: Mining mode (cpu_bitcoin, gpu_kaspa, dual)
            **kwargs: Additional parameters
            
        Returns:
            bool: True if started successfully
        """
        try:
            mode_enum = MiningMode(mode)
            
            if self.mode != MiningMode.STOPPED:
                logger.warning("Mining already active - stopping first")
                await self.stop_mining()
                
            if mode_enum == MiningMode.CPU_BITCOIN:
                return await self._start_cpu_bitcoin(**kwargs)
            elif mode_enum == MiningMode.GPU_KASPA:
                return await self._start_gpu_kaspa(**kwargs)
            elif mode_enum == MiningMode.GPU_BITCOIN:
                return await self._start_gpu_bitcoin(**kwargs)
            elif mode_enum == MiningMode.DUAL:
                return await self._start_dual(**kwargs)
            else:
                logger.error(f"Invalid mining mode: {mode}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start mining: {e}")
            return False
            
    async def _start_cpu_bitcoin(self, **kwargs) -> bool:
        """Start CPU Bitcoin mining
        
        Returns:
            bool: True if successful
        """
        btc_address = kwargs.get('btc_address') or self.config['btc_address']
        if not btc_address:
            logger.error("No Bitcoin address provided")
            return False
            
        logger.info("🔥 Starting CPU Bitcoin mining")
        logger.info("⚠️ Note: CPU Bitcoin mining is educational only")
        logger.info("Expected earnings: $0.0001-$0.0003/day")
        
        try:
            self.btc_miner = RealBTCMiner(
                btc_address=btc_address,
                num_workers=kwargs.get('num_workers')
            )
            
            # Start in thread
            def run_btc():
                self.btc_miner.run()
                
            threading.Thread(target=run_btc, daemon=True).start()
            
            self.mode = MiningMode.CPU_BITCOIN
            self._start_stats_updates()
            
            if self.event_bus:
                self.event_bus.publish("mining.started", {
                    "mode": "cpu_bitcoin",
                    "address": btc_address
                })
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to start CPU Bitcoin mining: {e}")
            return False
            
    async def _start_gpu_kaspa(self, **kwargs) -> bool:
        """Start GPU Kaspa mining
        
        Returns:
            bool: True if successful
        """
        kas_wallet = kwargs.get('kas_wallet') or self.config['kas_wallet']
        if not kas_wallet:
            logger.error("No Kaspa wallet provided")
            return False
            
        logger.info("🔥 Starting GPU Kaspa mining")
        logger.info("💰 Expected earnings: $0.40-$0.80/day (depending on GPU)")
        
        try:
            self.kas_miner = LolMinerGPU(
                wallet=kas_wallet,
                pool=kwargs.get('kas_pool') or self.config['kas_pool']
            )
            
            if not self.kas_miner.start():
                raise RuntimeError("Failed to start lolMiner")
                
            self.mode = MiningMode.GPU_KASPA
            self._start_stats_updates()
            
            if self.event_bus:
                self.event_bus.publish("mining.started", {
                    "mode": "gpu_kaspa",
                    "wallet": kas_wallet
                })
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to start GPU Kaspa mining: {e}")
            return False
            
    async def _start_gpu_bitcoin(self, **kwargs) -> bool:
        """Start GPU Bitcoin mining with Quantum acceleration
        
        Returns:
            bool: True if successful
        """
        btc_address = kwargs.get('btc_address') or self.config['btc_address']
        if not btc_address:
            logger.error("No Bitcoin address provided")
            return False
            
        logger.info("🔮 Starting Quantum-GPU Bitcoin mining")
        logger.info("Using quantum acceleration for SHA-256 optimization")
        
        try:
            from core.mining.gpu_miners import QuantumGPUMiner
            
            pool_host = kwargs.get('pool_host', 'btc.viabtc.io')  # Fixed: .io not .com
            pool_port = kwargs.get('pool_port', 3333)
            
            self.quantum_miner = QuantumGPUMiner(
                wallet=btc_address,
                pool_host=pool_host,
                pool_port=pool_port
            )
            
            if not self.quantum_miner.start():
                raise RuntimeError("Failed to start Quantum-GPU miner")
                
            self.mode = MiningMode.GPU_BITCOIN
            self._start_stats_updates()
            
            if self.event_bus:
                self.event_bus.publish("mining.started", {
                    "mode": "gpu_bitcoin_quantum",
                    "address": btc_address
                })
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Quantum-GPU Bitcoin mining: {e}")
            return False
        
    async def _start_dual(self, **kwargs) -> bool:
        """Start dual mining (BTC CPU + Kaspa GPU)
        
        Returns:
            bool: True if successful
        """
        btc_address = kwargs.get('btc_address') or self.config['btc_address']
        kas_wallet = kwargs.get('kas_wallet') or self.config['kas_wallet']
        
        if not btc_address or not kas_wallet:
            logger.error("Both Bitcoin and Kaspa addresses required for dual mining")
            return False
            
        logger.info("🔥🔥 Starting DUAL MINING: BTC (CPU) + KASPA (GPU)")
        logger.info("💰 Expected combined earnings: $0.40-$0.80/day")
        
        try:
            self.dual_miner = DualMiner(
                btc_address=btc_address,
                kas_wallet=kas_wallet
            )
            
            if not self.dual_miner.start():
                raise RuntimeError("Failed to start dual mining")
                
            self.mode = MiningMode.DUAL
            self._start_stats_updates()
            
            if self.event_bus:
                self.event_bus.publish("mining.started", {
                    "mode": "dual",
                    "btc_address": btc_address,
                    "kas_wallet": kas_wallet
                })
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to start dual mining: {e}")
            return False
            
    async def stop_mining(self) -> bool:
        """Stop all mining operations
        
        Returns:
            bool: True if successful
        """
        try:
            logger.info("Stopping mining...")
            
            self._stop_stats_updates()
            
            if self.btc_miner:
                # BTC miner stops when connection closes
                self.btc_miner = None
                
            if self.kas_miner:
                self.kas_miner.stop()
                self.kas_miner = None
                
            if self.dual_miner:
                self.dual_miner.stop()
                self.dual_miner = None
                
            if self.quantum_miner:
                self.quantum_miner.stop()
                self.quantum_miner = None
                
            old_mode = self.mode
            self.mode = MiningMode.STOPPED
            
            if self.event_bus:
                self.event_bus.publish("mining.stopped", {
                    "previous_mode": old_mode.value
                })
                
            logger.info("Mining stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping mining: {e}")
            return False
            
    def _start_stats_updates(self):
        """Start background stats update thread"""
        if self.stats_running:
            return
            
        self.stats_running = True
        self.stats_thread = threading.Thread(target=self._stats_loop, daemon=True)
        self.stats_thread.start()
        
    def _stop_stats_updates(self):
        """Stop background stats updates"""
        self.stats_running = False
        if self.stats_thread:
            self.stats_thread.join(timeout=2)
            
    def _stats_loop(self):
        """Background stats update loop"""
        while self.stats_running:
            try:
                if self.event_bus and self.mode != MiningMode.STOPPED:
                    stats = self.get_stats()
                    # EventBus.publish is sync (safe from any thread) - publish directly
                    try:
                        self.event_bus.publish("mining.stats", stats)
                        # GUI MiningFrame listens to mining.stats.update and mining.hashrate_update
                        self.event_bus.publish("mining.stats.update", stats)
                        # Best-effort hashrate event for the UI
                        raw_hps = None
                        try:
                            raw_hps = stats.get("raw_hps")
                        except Exception:
                            raw_hps = None
                        hr_val = None
                        try:
                            hr_val = stats.get("hashrate")
                        except Exception:
                            hr_val = None
                        import time as _time
                        payload = {"timestamp": _time.time()}
                        if raw_hps is not None:
                            payload["raw_hps"] = raw_hps
                        elif isinstance(hr_val, (int, float)):
                            payload["hashrate"] = float(hr_val)
                        self.event_bus.publish("mining.hashrate_update", payload)
                    except Exception:
                        pass
                    
            except:
                pass
                
            import time
            time.sleep(5)
            
    def get_stats(self) -> Dict[str, Any]:
        """Get current mining statistics
        
        Returns:
            dict: Mining statistics
        """
        stats = {
            'mode': self.mode.value,
            'hashrate': {},
            'shares': {},
            'efficiency': 0.0,
            'runtime': 0.0
        }
        
        try:
            if self.mode == MiningMode.CPU_BITCOIN and self.btc_miner:
                btc_stats = self.btc_miner.get_stats()
                stats.update(btc_stats)
                
            elif self.mode == MiningMode.GPU_KASPA and self.kas_miner:
                kas_stats = self.kas_miner.get_stats()
                stats.update(kas_stats)
                
            elif self.mode == MiningMode.DUAL and self.dual_miner:
                dual_stats = self.dual_miner.get_stats()
                stats.update(dual_stats)
                
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            
        return stats
        
    async def measure_cpu_hashrate(self, duration: float = 10.0) -> Dict[str, Any]:
        """Measure raw CPU hashrate
        
        Args:
            duration: Time in seconds to measure
            
        Returns:
            dict: Hashrate measurement results
        """
        logger.info(f"Measuring CPU hashrate for {duration} seconds...")
        
        # Run in thread pool to avoid blocking
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(measure_hashrate, duration)
            hps = future.result()
            
        tracker = HashrateTracker()
        formatted = tracker.format_hashrate(hps)
        
        result = {
            'raw_hps': hps,
            'formatted': formatted,
            'duration': duration,
            'timestamp': logger.info.__name__
        }
        
        logger.info(f"CPU hashrate: {formatted}")
        
        if self.event_bus:
            try:
                self.event_bus.publish("mining.hashrate_measured", result)
            except Exception:
                pass
            
        return result
        
    def get_mode(self) -> str:
        """Get current mining mode
        
        Returns:
            str: Current mode
        """
        return self.mode.value
        
    def is_mining(self) -> bool:
        """Check if mining is active
        
        Returns:
            bool: True if mining
        """
        return self.mode != MiningMode.STOPPED
