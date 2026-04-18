"""
Kingdom AI Advanced Mining Module
Complete Bitcoin, Kaspa, and GPU mining integration with:
- SHA-256 Ontology Mapping
- Quantum PoW Functions
- Intelligent Optimization
- Multi-Coin Coordination
"""

from core.mining.hashrate_tracker import HashrateTracker, GlobalHashrateTracker
from core.mining.bitcoin_miner import RealBTCMiner, measure_hashrate
from core.mining.gpu_miners import LolMinerGPU, DualMiner
from core.mining.advanced_mining_manager import AdvancedMiningManager, MiningMode
from core.mining.intelligent_optimizer import IntelligentMiningOptimizer, WorkloadBalancer
from core.mining.multi_coin_coordinator import MultiCoinCoordinator, ProfitSwitcher
from core.mining.sha256_ontology import SHA256OntologyMapper, SHA256AllCoinsMapper, SHA256Ontology
from core.mining.quantum_pow_functions import QuantumPoWEngine, QuantumMiningResult, QuantumAlgorithm

__all__ = [
    'HashrateTracker',
    'GlobalHashrateTracker',
    'RealBTCMiner',
    'measure_hashrate',
    'LolMinerGPU',
    'DualMiner',
    'AdvancedMiningManager',
    'MiningMode',
    'IntelligentMiningOptimizer',
    'WorkloadBalancer',
    'MultiCoinCoordinator',
    'ProfitSwitcher',
    'SHA256OntologyMapper',
    'SHA256AllCoinsMapper',
    'SHA256Ontology',
    'QuantumPoWEngine',
    'QuantumMiningResult',
    'QuantumAlgorithm'
]

__version__ = '2.0.0'
__author__ = 'Kingdom AI Development Team'
