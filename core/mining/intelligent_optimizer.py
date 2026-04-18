"""
Intelligent Mining Optimizer for Kingdom AI
Advanced CPU/GPU coordination and profitability optimization
"""

import logging
import asyncio
import time
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import deque
import multiprocessing as mp

logger = logging.getLogger("KingdomAI.IntelligentOptimizer")


@dataclass
class MiningPerformanceData:
    """Mining performance metrics"""
    coin: str
    algorithm: str
    hardware: str  # 'cpu' or 'gpu'
    hashrate: float
    power_consumption: float
    profitability: float
    timestamp: float
    efficiency: float  # hashes per watt


class IntelligentMiningOptimizer:
    """
    Advanced mining optimizer that coordinates CPU/GPU resources
    and maximizes profitability through intelligent decision making
    """
    
    def __init__(self, ollama_brain=None):
        """Initialize intelligent optimizer
        
        Args:
            ollama_brain: Optional Ollama AI instance for advanced optimization
        """
        self.ollama_brain = ollama_brain
        self.performance_history = deque(maxlen=10000)
        self.current_strategy = "balanced"
        
        # Resource allocation
        self.cpu_cores_available = mp.cpu_count()
        self.gpu_devices = []
        
        # Profitability tracking
        self.coin_profitability = {}
        self.algorithm_efficiency = {}
        
        # Optimization parameters
        self.optimization_interval = 60  # seconds
        self.learning_rate = 0.01
        
        logger.info("Intelligent Mining Optimizer initialized")
        
    async def optimize_resource_allocation(self, available_coins: List[str]) -> Dict[str, Dict]:
        """Optimize CPU/GPU allocation across multiple coins
        
        Args:
            available_coins: List of coins available for mining
            
        Returns:
            dict: Optimal resource allocation strategy
        """
        allocation = {
            'cpu': {},
            'gpu': {},
            'strategy': self.current_strategy
        }
        
        # Analyze profitability for each coin
        profitability_scores = {}
        for coin in available_coins:
            score = await self._calculate_profitability_score(coin)
            profitability_scores[coin] = score
            
        # Sort by profitability
        sorted_coins = sorted(
            profitability_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Allocate CPU resources
        cpu_allocation = self._allocate_cpu_resources(sorted_coins)
        allocation['cpu'] = cpu_allocation
        
        # Allocate GPU resources
        gpu_allocation = self._allocate_gpu_resources(sorted_coins)
        allocation['gpu'] = gpu_allocation
        
        logger.info(f"Optimized allocation: {len(cpu_allocation)} CPU tasks, {len(gpu_allocation)} GPU tasks")
        
        return allocation
        
    def _allocate_cpu_resources(self, sorted_coins: List[Tuple[str, float]]) -> Dict[str, int]:
        """Allocate CPU cores to coins based on profitability
        
        Args:
            sorted_coins: List of (coin, profitability_score) tuples
            
        Returns:
            dict: CPU core allocation per coin
        """
        allocation = {}
        
        if not sorted_coins:
            return allocation
            
        # Strategy: Allocate more cores to more profitable coins
        total_score = sum(score for _, score in sorted_coins)
        remaining_cores = self.cpu_cores_available
        
        for coin, score in sorted_coins:
            if remaining_cores <= 0:
                break
                
            # Allocate cores proportional to profitability
            cores_for_coin = max(1, int((score / total_score) * self.cpu_cores_available))
            cores_for_coin = min(cores_for_coin, remaining_cores)
            
            allocation[coin] = cores_for_coin
            remaining_cores -= cores_for_coin
            
        logger.debug(f"CPU allocation: {allocation}")
        return allocation
        
    def _allocate_gpu_resources(self, sorted_coins: List[Tuple[str, float]]) -> Dict[str, List[int]]:
        """Allocate GPUs to coins based on profitability and algorithm compatibility
        
        Args:
            sorted_coins: List of (coin, profitability_score) tuples
            
        Returns:
            dict: GPU device IDs allocated per coin
        """
        allocation = {}
        
        # GPU mining typically focuses on single most profitable coin
        # unless multiple GPUs available
        if sorted_coins and len(self.gpu_devices) > 0:
            most_profitable = sorted_coins[0][0]
            allocation[most_profitable] = list(range(len(self.gpu_devices)))
            
        logger.debug(f"GPU allocation: {allocation}")
        return allocation
        
    async def _calculate_profitability_score(self, coin: str) -> float:
        """Calculate profitability score for a coin
        
        Args:
            coin: Coin name
            
        Returns:
            float: Profitability score (higher is better)
        """
        # Base profitability from historical data
        base_prof = self.coin_profitability.get(coin, 0.5)
        
        # Factor in algorithm efficiency
        algo_eff = self.algorithm_efficiency.get(coin, 1.0)
        
        # Use Ollama brain for advanced prediction if available
        if self.ollama_brain:
            try:
                ai_prediction = await self._get_ai_profitability_prediction(coin)
                return base_prof * algo_eff * ai_prediction
            except:
                pass
                
        return base_prof * algo_eff
        
    async def _get_ai_profitability_prediction(self, coin: str) -> float:
        """Get AI-based profitability prediction from Ollama.
        
        Args:
            coin: Coin name
            
        Returns:
            float: AI prediction multiplier (0.1-2.0)
        """
        try:
            import aiohttp
            prompt = (
                f"You are a crypto mining profitability analyst. "
                f"Given current market conditions for {coin}, estimate a profitability "
                f"multiplier between 0.1 (very unprofitable) and 2.0 (very profitable). "
                f"1.0 means break-even. Reply with ONLY a decimal number."
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:11434/api/generate",
                    json={"model": "llama3", "prompt": prompt, "stream": False},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw = data.get("response", "").strip()
                        for token in raw.split():
                            try:
                                val = float(token)
                                return max(0.1, min(2.0, val))
                            except ValueError:
                                continue
            return 1.0
        except Exception as e:
            logger.debug(f"AI prediction unavailable: {e}")
            return 1.0
            
    def update_performance_data(self, data: MiningPerformanceData):
        """Update performance history with new data
        
        Args:
            data: Performance data point
        """
        self.performance_history.append(data)
        
        # Update profitability tracking
        self.coin_profitability[data.coin] = data.profitability
        
        # Update algorithm efficiency
        key = f"{data.coin}_{data.hardware}"
        if key not in self.algorithm_efficiency:
            self.algorithm_efficiency[key] = data.efficiency
        else:
            # Exponential moving average
            self.algorithm_efficiency[key] = (
                0.9 * self.algorithm_efficiency[key] + 0.1 * data.efficiency
            )
            
    def get_optimization_recommendations(self) -> List[str]:
        """Get optimization recommendations based on performance history
        
        Returns:
            list: List of recommendation strings
        """
        recommendations = []
        
        if len(self.performance_history) < 100:
            recommendations.append("Gathering performance data...")
            return recommendations
            
        # Analyze recent performance
        recent = list(self.performance_history)[-100:]
        
        # Check CPU efficiency
        cpu_data = [d for d in recent if d.hardware == 'cpu']
        if cpu_data:
            avg_cpu_eff = np.mean([d.efficiency for d in cpu_data])
            if avg_cpu_eff < 100000:  # Below 100 KH/s per watt
                recommendations.append("CPU efficiency low - consider upgrading to PyPy3 for 10x boost")
                
        # Check GPU efficiency
        gpu_data = [d for d in recent if d.hardware == 'gpu']
        if gpu_data:
            avg_gpu_eff = np.mean([d.efficiency for d in gpu_data])
            if avg_gpu_eff > 1e9:  # Above 1 GH/s per watt
                recommendations.append("GPU performing excellently - maintain current settings")
            else:
                recommendations.append("GPU efficiency could improve - check overclock settings")
                
        # Check profitability trends
        prof_trend = self._calculate_profitability_trend()
        if prof_trend < 0:
            recommendations.append("Profitability declining - consider switching coins")
        elif prof_trend > 0.1:
            recommendations.append("Profitability increasing - maintain current strategy")
            
        return recommendations
        
    def _calculate_profitability_trend(self) -> float:
        """Calculate profitability trend from recent history
        
        Returns:
            float: Trend coefficient (positive = improving, negative = declining)
        """
        if len(self.performance_history) < 50:
            return 0.0
            
        recent = list(self.performance_history)[-50:]
        profitability_values = [d.profitability for d in recent]
        
        # Simple linear regression
        x = np.arange(len(profitability_values))
        y = np.array(profitability_values)
        
        coeffs = np.polyfit(x, y, 1)
        return coeffs[0]  # Slope
        
    async def adaptive_difficulty_adjustment(self, current_difficulty: int, 
                                            target_block_time: float = 600.0) -> int:
        """Adaptively adjust mining difficulty based on performance
        
        Args:
            current_difficulty: Current difficulty bits
            target_block_time: Target block time in seconds
            
        Returns:
            int: Adjusted difficulty bits
        """
        if len(self.performance_history) < 10:
            return current_difficulty
            
        # Calculate average block solve time
        recent = list(self.performance_history)[-10:]
        avg_hashrate = np.mean([d.hashrate for d in recent])
        
        # Estimate blocks per second
        estimated_bps = avg_hashrate / (2 ** current_difficulty)
        estimated_block_time = 1.0 / estimated_bps if estimated_bps > 0 else float('inf')
        
        # Adjust difficulty if block time differs significantly
        if estimated_block_time < target_block_time * 0.5:
            # Too fast - increase difficulty
            return current_difficulty + 1
        elif estimated_block_time > target_block_time * 2.0:
            # Too slow - decrease difficulty  
            return max(1, current_difficulty - 1)
            
        return current_difficulty
        
    def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics
        
        Returns:
            dict: Statistics dictionary
        """
        stats = {
            'performance_samples': len(self.performance_history),
            'current_strategy': self.current_strategy,
            'cpu_cores_allocated': self.cpu_cores_available,
            'gpu_devices': len(self.gpu_devices),
            'tracked_coins': len(self.coin_profitability),
            'algorithm_efficiencies': self.algorithm_efficiency.copy(),
            'coin_profitability': self.coin_profitability.copy()
        }
        
        if len(self.performance_history) > 0:
            recent = list(self.performance_history)[-100:]
            stats['avg_hashrate'] = np.mean([d.hashrate for d in recent])
            stats['avg_profitability'] = np.mean([d.profitability for d in recent])
            stats['profitability_trend'] = self._calculate_profitability_trend()
            
        return stats
        
    async def optimize_with_ai(self, mining_context: Dict[str, Any]) -> Dict[str, Any]:
        """Use Ollama AI brain for advanced optimization
        
        Args:
            mining_context: Current mining context and metrics
            
        Returns:
            dict: AI-generated optimization strategy
        """
        if not self.ollama_brain:
            logger.warning("Ollama brain not available for AI optimization")
            return {'strategy': 'default'}
            
        try:
            context_str = self._prepare_ai_context(mining_context)

            import aiohttp, json as _json
            prompt = (
                "You are a mining optimization AI for Kingdom AI. "
                "Given the following mining context, recommend an optimal strategy. "
                "Return a JSON object with keys: recommended_coins (list of strings), "
                "resource_allocation (string describing CPU/GPU split), "
                "expected_improvement (float multiplier), reasoning (string). "
                f"\n\nContext:\n{context_str}\n\nReply with ONLY valid JSON."
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:11434/api/generate",
                    json={"model": "llama3", "prompt": prompt, "stream": False},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw = data.get("response", "").strip()
                        start = raw.find("{")
                        end = raw.rfind("}") + 1
                        if start >= 0 and end > start:
                            ai_response = _json.loads(raw[start:end])
                            for key in ("recommended_coins", "resource_allocation",
                                        "expected_improvement", "reasoning"):
                                if key not in ai_response:
                                    raise ValueError(f"Missing key: {key}")
                            logger.info(f"AI optimization: {ai_response['reasoning']}")
                            return ai_response

            logger.warning("Ollama returned no usable response, using heuristic fallback")
            return self._heuristic_optimization(mining_context)
            
        except Exception as e:
            logger.error(f"AI optimization failed: {e}")
            return self._heuristic_optimization(mining_context)

    def _heuristic_optimization(self, mining_context: Dict[str, Any]) -> Dict[str, Any]:
        """Heuristic fallback when Ollama is unavailable."""
        coins = list(self.coin_profitability.keys()) or ['bitcoin']
        sorted_coins = sorted(coins, key=lambda c: self.coin_profitability.get(c, 0), reverse=True)
        best = sorted_coins[:2]
        has_gpu = len(self.gpu_devices) > 0
        allocation = f"gpu_{best[0]}_cpu_{best[1]}" if len(best) > 1 and has_gpu else f"cpu_{best[0]}"
        return {
            'recommended_coins': best,
            'resource_allocation': allocation,
            'expected_improvement': 1.05,
            'reasoning': f"Heuristic: top coins by profitability are {best}"
        }

    def _prepare_ai_context(self, mining_context: Dict[str, Any]) -> str:
        """Prepare mining context for AI analysis
        
        Args:
            mining_context: Mining metrics and context
            
        Returns:
            str: Formatted context string
        """
        context_parts = [
            f"Current Strategy: {self.current_strategy}",
            f"CPU Cores: {self.cpu_cores_available}",
            f"GPU Devices: {len(self.gpu_devices)}",
            f"Performance Samples: {len(self.performance_history)}"
        ]
        
        if self.coin_profitability:
            top_coins = sorted(
                self.coin_profitability.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            context_parts.append(f"Top Profitable: {[c for c, _ in top_coins]}")
            
        return "\n".join(context_parts)


class WorkloadBalancer:
    """Balance mining workload across CPU and GPU resources"""
    
    def __init__(self):
        self.cpu_workload = 0.0  # 0.0 to 1.0
        self.gpu_workload = 0.0  # 0.0 to 1.0
        self.target_cpu_utilization = 0.95
        self.target_gpu_utilization = 0.98
        
    def balance_workload(self, cpu_hashrate: float, gpu_hashrate: float,
                        cpu_max: float, gpu_max: float) -> Tuple[float, float]:
        """Balance workload to maintain target utilization
        
        Args:
            cpu_hashrate: Current CPU hashrate
            gpu_hashrate: Current GPU hashrate
            cpu_max: Maximum CPU hashrate
            gpu_max: Maximum GPU hashrate
            
        Returns:
            tuple: (cpu_multiplier, gpu_multiplier) for workload adjustment
        """
        # Calculate current utilization
        cpu_util = cpu_hashrate / cpu_max if cpu_max > 0 else 0
        gpu_util = gpu_hashrate / gpu_max if gpu_max > 0 else 0
        
        # Calculate adjustment multipliers
        cpu_mult = 1.0
        gpu_mult = 1.0
        
        if cpu_util < self.target_cpu_utilization * 0.9:
            # CPU underutilized - increase load
            cpu_mult = 1.1
        elif cpu_util > self.target_cpu_utilization:
            # CPU overutilized - decrease load
            cpu_mult = 0.9
            
        if gpu_util < self.target_gpu_utilization * 0.9:
            # GPU underutilized - increase load
            gpu_mult = 1.1
        elif gpu_util > self.target_gpu_utilization:
            # GPU overutilized - decrease load
            gpu_mult = 0.9
            
        logger.debug(f"Workload balance: CPU {cpu_util:.2%} (x{cpu_mult:.2f}), GPU {gpu_util:.2%} (x{gpu_mult:.2f})")
        
        return cpu_mult, gpu_mult
        
    def get_optimal_thread_count(self, cpu_cores: int, current_hashrate: float,
                                target_hashrate: float) -> int:
        """Calculate optimal thread count for current conditions
        
        Args:
            cpu_cores: Available CPU cores
            current_hashrate: Current hashrate
            target_hashrate: Target hashrate
            
        Returns:
            int: Optimal thread count
        """
        if current_hashrate >= target_hashrate * 0.95:
            # Meeting target - maintain current
            return cpu_cores
            
        # Calculate scaling factor
        scale = target_hashrate / current_hashrate if current_hashrate > 0 else 1.0
        optimal = int(cpu_cores * scale)
        
        # Clamp to reasonable range
        return max(1, min(optimal, cpu_cores * 2))
