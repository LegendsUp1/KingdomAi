"""
Advanced Hashrate Tracking System for Kingdom AI Mining
Real-time hash rate measurement with rolling averages and performance metrics
"""

import time
import logging
from datetime import datetime
from collections import deque
from typing import Dict, List, Optional
import multiprocessing as mp

logger = logging.getLogger("KingdomAI.HashrateTracker")


class HashrateTracker:
    """High-precision, real-time hashrate tracker with rolling averages"""
    
    def __init__(self, intervals: List[int] = None):
        """
        Initialize hashrate tracker
        
        Args:
            intervals: List of time intervals in seconds for rolling averages (default: [1, 5, 15, 60])
        """
        self.intervals = intervals or [1, 5, 15, 60]
        self.history = {i: deque() for i in self.intervals}
        self.start_time = time.time()
        self.total_hashes = mp.Value('Q', 0)  # Thread-safe counter
        self.last_print = 0
        self.shares = 0
        self.accepted = 0
        self.rejected = 0
        
    def add_hashes(self, count: int):
        """Add hash count to tracker
        
        Args:
            count: Number of hashes computed
        """
        now = time.time()
        with self.total_hashes.get_lock():
            self.total_hashes.value += count
            
        for interval in self.intervals:
            self.history[interval].append((now, count))
            # Clean old entries
            cutoff = now - interval
            while self.history[interval] and self.history[interval][0][0] < cutoff:
                self.history[interval].popleft()
                
    def add_hashrate(self, hps: float):
        """Add instantaneous hashrate measurement
        
        Args:
            hps: Hashes per second
        """
        now = time.time()
        for interval in self.intervals:
            self.history[interval].append((now, hps))
            # Rolling average - keep only recent data
            if len(self.history[interval]) > interval:
                self.history[interval].popleft()
                
    def get_hashrate(self, interval: int) -> float:
        """Get average hashrate for specified interval
        
        Args:
            interval: Time interval in seconds
            
        Returns:
            float: Average hashes per second
        """
        if not self.history[interval]:
            return 0.0
        total = sum(c for _, c in self.history[interval])
        elapsed = time.time() - self.history[interval][0][0]
        return total / max(elapsed, 0.001) if elapsed > 0 else 0.0
        
    def get_avg(self, interval: int) -> float:
        """Get rolling average for interval (for pre-computed rates)
        
        Args:
            interval: Time interval in seconds
            
        Returns:
            float: Average hashrate
        """
        if not self.history[interval]:
            return 0.0
        times, rates = zip(*self.history[interval])
        return sum(rates) / len(rates) if rates else 0.0
        
    def format_hashrate(self, hps: float) -> str:
        """Convert H/s to human-readable format
        
        Args:
            hps: Hashes per second
            
        Returns:
            str: Formatted hashrate (e.g., "1.23 GH/s")
        """
        units = [
            ("H/s", 1),
            ("KH/s", 1e3),
            ("MH/s", 1e6),
            ("GH/s", 1e9),
            ("TH/s", 1e12),
            ("PH/s", 1e15),
            ("EH/s", 1e18),
            ("ZH/s", 1e21)
        ]
        
        for unit, scale in reversed(units):
            if hps >= scale:
                return f"{hps/scale:.2f} {unit}"
        return f"{hps:.2f} H/s"
        
    def format_hps(self, hps: float) -> str:
        """Alias for format_hashrate"""
        return self.format_hashrate(hps)
        
    def update_shares(self, accepted: bool = True):
        """Update share statistics
        
        Args:
            accepted: True if share was accepted, False if rejected
        """
        self.shares += 1
        if accepted:
            self.accepted += 1
        else:
            self.rejected += 1
            
    def get_efficiency(self) -> float:
        """Get share acceptance efficiency
        
        Returns:
            float: Percentage of accepted shares (0-100)
        """
        if self.shares == 0:
            return 100.0
        return (self.accepted / self.shares) * 100
        
    def get_runtime(self) -> float:
        """Get total runtime in seconds
        
        Returns:
            float: Runtime in seconds
        """
        return time.time() - self.start_time
        
    def print_status(self, mode: str = "MINING"):
        """Print current hashrate status
        
        Args:
            mode: Mining mode label (e.g., "GPU", "CPU", "BTC")
        """
        now = time.time()
        if now - self.last_print < 1.0:  # Throttle to 1 second
            return
        self.last_print = now
        
        print(f"\n{'='*80}")
        print(f" 🔥 LIVE {mode} HASHRATE @ {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*80}")
        
        for i in self.intervals:
            avg = self.get_hashrate(i)
            print(f"   {i:2d}s AVG: {self.format_hashrate(avg):>12}")
            
        runtime = self.get_runtime()
        efficiency = self.get_efficiency()
        
        print(f"{'-'*80}")
        print(f"   Total Hashes: {self.total_hashes.value:,} | Runtime: {runtime/60:.1f} min")
        print(f"   Shares: {self.shares} | Acc: {self.accepted} | Rej: {self.rejected}")
        print(f"   Efficiency: {efficiency:.1f}%")
        print(f"{'='*80}\n")
        
    def get_stats(self) -> Dict:
        """Get complete statistics dictionary
        
        Returns:
            dict: Statistics including hashrates, shares, efficiency
        """
        return {
            'hashrates': {
                f'{i}s': self.get_hashrate(i)
                for i in self.intervals
            },
            'formatted_hashrates': {
                f'{i}s': self.format_hashrate(self.get_hashrate(i))
                for i in self.intervals
            },
            'total_hashes': self.total_hashes.value,
            'runtime': self.get_runtime(),
            'shares': {
                'total': self.shares,
                'accepted': self.accepted,
                'rejected': self.rejected,
                'efficiency': self.get_efficiency()
            },
            'timestamp': datetime.now().isoformat()
        }
        
    def reset(self):
        """Reset all statistics"""
        self.history = {i: deque() for i in self.intervals}
        self.start_time = time.time()
        with self.total_hashes.get_lock():
            self.total_hashes.value = 0
        self.shares = 0
        self.accepted = 0
        self.rejected = 0
        logger.info("Hashrate tracker reset")


class GlobalHashrateTracker:
    """Global singleton hashrate tracker for system-wide monitoring"""
    
    _instance: Optional[HashrateTracker] = None
    
    @classmethod
    def get_instance(cls) -> HashrateTracker:
        """Get or create global hashrate tracker instance
        
        Returns:
            HashrateTracker: Global tracker instance
        """
        if cls._instance is None:
            cls._instance = HashrateTracker()
            logger.info("Global hashrate tracker initialized")
        return cls._instance
        
    @classmethod
    def reset_instance(cls):
        """Reset the global tracker instance"""
        if cls._instance:
            cls._instance.reset()
        cls._instance = None
