#!/usr/bin/env python3
"""
THOTH AI LIVE INTEGRATION - Neural Multi-Model Orchestration System
Connect Ollama Brain to ALL Live Systems with NEURAL NETWORK-LIKE MODEL COLLABORATION

ALL MODELS WORK SIMULTANEOUSLY LIKE NEURONS:
- Self-organizing to solve tasks
- Communicating with each other
- Understanding the entire Kingdom AI system
- Operating all 10 tabs and subsystems autonomously

NO MOCK DATA - 100% REAL CONTROL
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict

from enum import Enum
import json
import aiohttp

import numpy as np

from core.cql_cvar_policy import ConservativeSizingPolicy
from core.position_sizing import PositionSizer, PositionSizingInputs
from core.position_monitor import PositionMonitor, get_position_monitor, initialize_position_monitor
from core.coin_accumulation_intelligence import (
    CoinAccumulationIntelligence,
    get_coin_accumulation_intelligence,
)

from core.real_exchange_executor import OrderType as ExchangeOrderType
from core.real_exchange_executor import OrderSide as ExchangeOrderSide

logger = logging.getLogger(__name__)


# ============================================================================
# NEURAL MULTI-MODEL ORCHESTRATION SYSTEM - SOTA 2025
# All models communicate like neurons, self-organizing to solve tasks
# ============================================================================

class ModelRole(Enum):
    """Specialized roles for each model in the neural network"""
    COORDINATOR = "coordinator"      # Orchestrates all other models
    TRADER = "trader"                # Trading decisions and analysis
    CODER = "coder"                  # Code generation and strategy creation
    ANALYST = "analyst"              # Data analysis and pattern recognition
    REASONER = "reasoner"            # Complex reasoning and planning
    CREATIVE = "creative"            # Creative solutions and alternatives
    VALIDATOR = "validator"          # Validates and verifies outputs
    EXECUTOR = "executor"            # Executes operations and commands


@dataclass
class NeuralModelNode:
    """A single model node in the neural network - acts like a neuron"""
    model_name: str
    role: ModelRole
    specializations: List[str] = field(default_factory=list)
    activation: float = 0.0  # Current activation level (0.0 to 1.0)
    connections: List[str] = field(default_factory=list)  # Connected model names
    last_output: Optional[Dict] = None
    processing: bool = False
    success_rate: float = 1.0  # Track success for adaptive routing


@dataclass
class NeuralTask:
    """A task to be processed by the neural model network"""
    task_id: str
    task_type: str  # trading, coding, analysis, general, system_operation
    prompt: str
    context: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10, higher = more urgent
    required_roles: List[ModelRole] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    consensus: Optional[Dict] = None
    completed: bool = False


class NeuralModelOrchestrator:
    """
    NEURAL MULTI-MODEL ORCHESTRATION SYSTEM
    
    All Ollama models work simultaneously like neurons in a brain:
    - Each model has a specialized role
    - Models communicate and share information
    - Self-organizing to solve complex tasks
    - Consensus-based decision making
    - Parallel processing for speed
    """
    
    # Available models mapped to their neural roles
    MODEL_NEURAL_MAPPING = {
        # Primary reasoning models
        "llama3.2:latest": NeuralModelNode("llama3.2:latest", ModelRole.COORDINATOR, ["orchestration", "planning", "synthesis"]),
        "llama3.1:latest": NeuralModelNode("llama3.1:latest", ModelRole.ANALYST, ["data_analysis", "pattern_recognition"]),
        "llama3:latest": NeuralModelNode("llama3:latest", ModelRole.EXECUTOR, ["task_execution", "command_processing"]),
        "llama2:latest": NeuralModelNode("llama2:latest", ModelRole.VALIDATOR, ["verification", "fact_checking"]),
        
        # Specialized models
        "qwen2.5:latest": NeuralModelNode("qwen2.5:latest", ModelRole.ANALYST, ["multilingual", "factual_analysis", "research"]),
        "mistral:latest": NeuralModelNode("mistral:latest", ModelRole.CREATIVE, ["creative_solutions", "alternatives", "brainstorming"]),
        "codellama:latest": NeuralModelNode("codellama:latest", ModelRole.CODER, ["code_generation", "debugging", "strategy_code"]),
        "deepseek-coder:latest": NeuralModelNode("deepseek-coder:latest", ModelRole.CODER, ["advanced_coding", "algorithm_design"]),
        "deepseek-r1:8b": NeuralModelNode("deepseek-r1:8b", ModelRole.REASONER, ["complex_reasoning", "chain_of_thought", "planning"]),
        
        # Trading specialists
        "phi3:latest": NeuralModelNode("phi3:latest", ModelRole.TRADER, ["quick_analysis", "market_signals"]),
        "gemma2:latest": NeuralModelNode("gemma2:latest", ModelRole.TRADER, ["trading_decisions", "risk_assessment"]),
        "mixtral:latest": NeuralModelNode("mixtral:latest", ModelRole.COORDINATOR, ["moe_routing", "ensemble_decisions"]),
    }
    
    def __init__(self, event_bus=None, api_endpoint: str = None):
        self.event_bus = event_bus
        try:
            from core.ollama_gateway import get_ollama_url
            self._ollama_base = get_ollama_url()
            if api_endpoint is None:
                self.api_endpoint = self._ollama_base.rstrip("/") + "/api"
            else:
                self.api_endpoint = api_endpoint
        except ImportError:
            try:
                from core.ollama_config import get_ollama_base_url
                self._ollama_base = get_ollama_base_url()
                if api_endpoint is None:
                    self.api_endpoint = self._ollama_base.rstrip("/") + "/api"
                else:
                    self.api_endpoint = api_endpoint
            except Exception:
                self._ollama_base = "http://localhost:11434"
                self.api_endpoint = api_endpoint or "http://localhost:11434/api"
        self.active_models: Dict[str, NeuralModelNode] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        self._processing_task: Optional[asyncio.Task] = None
        
        # Neural network state
        self.global_context: Dict[str, Any] = {}
        self.shared_memory: Dict[str, Any] = {}  # Shared between all models
        self.consensus_threshold = 0.7  # 70% agreement needed for consensus
        
        logger.info("🧠 Neural Multi-Model Orchestrator initialized")
    
    async def initialize(self) -> bool:
        """Initialize the neural network by discovering available models"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_endpoint}/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        available = [m.get('name', '') for m in data.get('models', [])]
                        
                        # Activate available models as neural nodes
                        for model_name, node in self.MODEL_NEURAL_MAPPING.items():
                            base_name = model_name.split(':')[0]
                            if any(base_name in m for m in available):
                                # Find exact match
                                exact = next((m for m in available if base_name in m), model_name)
                                node.model_name = exact
                                self.active_models[exact] = node
                                logger.info(f"🧠 Neural node activated: {exact} as {node.role.value}")
                        
                        # Establish neural connections (all models connect to coordinator)
                        self._establish_neural_connections()
                        
                        logger.info(f"🧠 Neural network ready with {len(self.active_models)} active nodes")
                        return True
            return False
        except Exception as e:
            logger.error(f"Failed to initialize neural network: {e}")
            return False
    
    def _establish_neural_connections(self):
        """Establish connections between neural model nodes"""
        coordinators = [n for n in self.active_models.values() if n.role == ModelRole.COORDINATOR]
        
        for model_name, node in self.active_models.items():
            # Connect all nodes to coordinators
            for coord in coordinators:
                if coord.model_name != model_name:
                    node.connections.append(coord.model_name)
            
            # Connect same-role nodes for collaboration
            for other_name, other_node in self.active_models.items():
                if other_name != model_name and other_node.role == node.role:
                    node.connections.append(other_name)
    
    async def process_task_neural(self, task: NeuralTask) -> Dict[str, Any]:
        """
        Process a task using the neural model network.
        All relevant models work simultaneously and reach consensus.
        """
        logger.info(f"🧠 Neural processing task: {task.task_type} (priority: {task.priority})")
        
        # 1. Select models based on task type
        selected_models = self._select_models_for_task(task)
        
        if not selected_models:
            # Fallback to any available model
            selected_models = list(self.active_models.values())[:3]
        
        # 2. Prepare context with Kingdom AI system knowledge
        enhanced_prompt = self._enhance_prompt_with_system_knowledge(task)
        
        # 3. Run all selected models in parallel (like neurons firing)
        tasks = []
        for node in selected_models:
            tasks.append(self._query_model_async(node, enhanced_prompt, task.context))
        
        # 4. Gather all responses simultaneously
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 5. Process responses and build consensus
        valid_responses = []
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                logger.warning(f"Model {selected_models[i].model_name} failed: {resp}")
                selected_models[i].success_rate *= 0.9  # Reduce success rate
            else:
                valid_responses.append({
                    "model": selected_models[i].model_name,
                    "role": selected_models[i].role.value,
                    "response": resp
                })
                selected_models[i].success_rate = min(1.0, selected_models[i].success_rate * 1.1)
        
        # 6. Synthesize consensus from all neural outputs
        consensus = await self._synthesize_consensus(valid_responses, task)
        
        task.results = {
            "individual_responses": valid_responses,
            "consensus": consensus,
            "models_used": [n.model_name for n in selected_models],
            "timestamp": datetime.now().isoformat()
        }
        task.completed = True
        
        logger.info(f"🧠 Neural consensus reached using {len(valid_responses)} models")
        return task.results
    
    def _select_models_for_task(self, task: NeuralTask) -> List[NeuralModelNode]:
        """Select the best models for a given task type"""
        selected = []
        
        # Task type to role mapping
        role_mapping = {
            "trading": [ModelRole.TRADER, ModelRole.ANALYST, ModelRole.REASONER],
            "coding": [ModelRole.CODER, ModelRole.VALIDATOR],
            "analysis": [ModelRole.ANALYST, ModelRole.REASONER, ModelRole.COORDINATOR],
            "general": [ModelRole.COORDINATOR, ModelRole.CREATIVE, ModelRole.VALIDATOR],
            "system_operation": [ModelRole.EXECUTOR, ModelRole.COORDINATOR, ModelRole.VALIDATOR],
            "mining": [ModelRole.ANALYST, ModelRole.EXECUTOR, ModelRole.CODER],
            "blockchain": [ModelRole.CODER, ModelRole.ANALYST, ModelRole.VALIDATOR],
            "wallet": [ModelRole.EXECUTOR, ModelRole.VALIDATOR, ModelRole.ANALYST],
        }
        
        required_roles = role_mapping.get(task.task_type, [ModelRole.COORDINATOR])
        
        # Select models by role, prioritizing by success rate
        for role in required_roles:
            role_models = [n for n in self.active_models.values() if n.role == role]
            role_models.sort(key=lambda x: x.success_rate, reverse=True)
            if role_models:
                selected.append(role_models[0])
        
        # Always include a coordinator for orchestration
        if not any(n.role == ModelRole.COORDINATOR for n in selected):
            coordinators = [n for n in self.active_models.values() if n.role == ModelRole.COORDINATOR]
            if coordinators:
                selected.append(coordinators[0])
        
        return selected
    
    def _enhance_prompt_with_system_knowledge(self, task: NeuralTask) -> str:
        """Enhance the prompt with full Kingdom AI system knowledge"""
        system_knowledge = """You are part of THOTH AI's NEURAL MULTI-MODEL BRAIN - a network of AI models working together like neurons.

## YOUR NEURAL NETWORK ROLE
You are one of multiple AI models processing this task simultaneously. Your response will be combined with others to form a consensus decision. Be precise, factual, and action-oriented.

## KINGDOM AI SYSTEM YOU CONTROL
You have FULL ACCESS to operate ALL of these systems:

### 10 TABS YOU CONTROL:
1. **Dashboard**: System health, Redis Quantum Nexus (port 6380), performance metrics
2. **Trading**: Live order books, trades feeds, price charts, arbitrage, AI strategies, meme scanner, quantum trading, risk management
3. **Mining**: 64 PoW coins, GPU monitoring, pool management, quantum integration
4. **Thoth AI (YOU)**: Ollama brain (12+ models), voice synthesis, MCP integration
5. **Code Generator**: Multi-language code generation, strategy templates
6. **API Key Manager**: 212+ API keys for exchanges, blockchains, data providers
7. **VR System**: VR trading interface, 6DOF tracking, gesture control
8. **Wallet**: 467+ blockchain networks, cross-chain swaps, portfolio analytics
9. **Blockchain**: Smart contracts, KingdomWeb3, transaction monitoring
10. **Settings**: System configuration, trading parameters, AI settings

### LIVE SYSTEMS CONNECTED:
- **Exchanges**: Kraken, Binance US, HTX, Bitstamp, BTCC, OANDA (forex), Alpaca (stocks)
- **Executors**: RealExchangeExecutor (CCXT), RealStockExecutor (Alpaca)
- **Data Feeds**: Live order books, trades, OHLCV, sentiment, arbitrage opportunities
- **Risk Management**: Portfolio analytics, risk scoring, leverage monitoring
- **AI Strategies**: Deep learning, meta-learning, quantum-enhanced predictions
- **Blockchain**: Ethereum, Bitcoin, Polygon, BSC, Arbitrum, Optimism, Base, Avalanche
- **Mining**: 64 PoW algorithms, GPU pools, quantum mining optimization

### AVAILABLE OPERATIONS:
- Execute trades on any connected exchange
- Generate and deploy trading strategies
- Monitor and manage mining operations
- Interact with smart contracts
- Manage wallets across 467+ blockchains
- Analyze market data in real-time
- Control VR trading interface
- Generate code for any system component

### SOTA 2026: VOICE & TEXT COMMAND CONTROL
Users can control the ENTIRE system via natural language commands in chat or voice:

**Device Commands**: "scan devices", "list devices", "enable device [name]"
**Software Automation**: "list windows", "connect to [software]", "send keys [text]", "click at X,Y"
**Trading**: "buy [amount] [symbol]", "sell [amount] [symbol]", "show portfolio", "check price [symbol]"
**Mining**: "start mining [coin]", "stop mining", "show hashrate"
**Wallet**: "show balance", "send [amount] [token] to [address]"
**Navigation**: "go to trading", "open wallet", "show mining", "switch to settings"
**UI Control**: "scroll up", "scroll down", "fullscreen", "refresh"

When users give these commands, you should acknowledge the action and provide helpful context.
See docs/SOTA_2026_MCP_VOICE_COMMANDS.md for complete command reference.

## RESPONSE FORMAT
Provide a clear, actionable response. If this is a trading decision, include: action (BUY/SELL/HOLD), confidence (0-100), reasoning.
If this is a system operation, include: operation, parameters, expected_outcome.
"""
        return f"{system_knowledge}\n\n## CURRENT TASK:\n{task.prompt}\n\n## CONTEXT:\n{json.dumps(task.context, indent=2)}"
    
    async def _query_model_async(self, node: NeuralModelNode, prompt: str, context: Dict) -> Dict[str, Any]:
        """Query a single model asynchronously"""
        node.processing = True
        node.activation = 1.0
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": node.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_ctx": 8192,
                        "temperature": 0.7,
                        "top_p": 0.9,
                    }
                }
                
                async with session.post(f"{self.api_endpoint}/generate", json=payload, timeout=aiohttp.ClientTimeout(total=120)) as response:
                    if response.status == 200:
                        result = await response.json()
                        node.last_output = result
                        return {
                            "text": result.get("response", ""),
                            "model": node.model_name,
                            "role": node.role.value
                        }
                    else:
                        raise ConnectionError(f"Model returned status {response.status}")
        finally:
            node.processing = False
            node.activation = 0.5
    
    async def _synthesize_consensus(self, responses: List[Dict], task: NeuralTask) -> Dict[str, Any]:
        """Synthesize a consensus from multiple model responses"""
        if not responses:
            return {"error": "No valid responses to synthesize"}
        
        if len(responses) == 1:
            return responses[0]["response"]
        
        # For trading tasks, aggregate decisions
        if task.task_type == "trading":
            return self._trading_consensus(responses)
        
        # For other tasks, use coordinator to synthesize
        coordinator = next((n for n in self.active_models.values() if n.role == ModelRole.COORDINATOR), None)
        
        if coordinator:
            synthesis_prompt = f"""You are the COORDINATOR model. Synthesize these responses from other neural models into a single coherent response:

{json.dumps([r['response'] for r in responses], indent=2)}

Provide a unified response that combines the best insights from all models."""
            
            try:
                result = await self._query_model_async(coordinator, synthesis_prompt, {})
                return {
                    "synthesized": result.get("text", ""),
                    "source_count": len(responses),
                    "coordinator": coordinator.model_name
                }
            except:
                pass
        
        # Fallback: return first response
        return responses[0]["response"]
    
    def _trading_consensus(self, responses: List[Dict]) -> Dict[str, Any]:
        """Build consensus for trading decisions"""
        actions = {"BUY": 0, "SELL": 0, "HOLD": 0}
        confidences = []
        reasonings = []
        
        for resp in responses:
            text = resp.get("response", {}).get("text", "")
            
            # Parse action
            if "BUY" in text.upper():
                actions["BUY"] += 1
            elif "SELL" in text.upper():
                actions["SELL"] += 1
            else:
                actions["HOLD"] += 1
            
            # Try to extract confidence
            import re
            conf_match = re.search(r'confidence[:\s]*(\d+)', text.lower())
            if conf_match:
                confidences.append(int(conf_match.group(1)))
            
            reasonings.append(f"[{resp.get('model', 'unknown')}]: {text[:200]}")
        
        # Determine consensus action
        total_votes = sum(actions.values())
        consensus_action = max(actions.keys(), key=lambda k: actions[k])
        consensus_strength = actions[consensus_action] / total_votes if total_votes > 0 else 0
        
        return {
            "action": consensus_action,
            "confidence": sum(confidences) / len(confidences) if confidences else 50,
            "consensus_strength": consensus_strength * 100,
            "votes": actions,
            "reasoning": f"Neural consensus ({len(responses)} models): " + "; ".join(reasonings[:3])
        }


# Global orchestrator instance
_neural_orchestrator: Optional[NeuralModelOrchestrator] = None

def get_neural_orchestrator(event_bus=None) -> NeuralModelOrchestrator:
    """Get or create the global neural orchestrator"""
    global _neural_orchestrator
    if _neural_orchestrator is None:
        _neural_orchestrator = NeuralModelOrchestrator(event_bus=event_bus)
    return _neural_orchestrator


class ThothLiveIntegration:
    """
    Thoth AI Live Integration with NEURAL MULTI-MODEL ORCHESTRATION
    
    Connects Ollama brain to ALL live trading and blockchain systems.
    ALL MODELS WORK SIMULTANEOUSLY LIKE NEURONS:
    - Self-organizing to solve tasks
    - Communicating with each other
    - Understanding the entire Kingdom AI system
    - Operating all 10 tabs and subsystems autonomously
    
    Gives Thoth autonomous control with real transaction capabilities.
    """
    
    def __init__(self, event_bus=None, api_keys: Optional[Dict] = None):
        """
        Initialize Thoth Live Integration with Neural Multi-Model Orchestration.
        
        Args:
            event_bus: Event bus for system communication
            api_keys: All API keys from APIKeyManager
        """
        self.event_bus = event_bus
        self.api_keys = api_keys or {}
        
        # NEURAL MULTI-MODEL ORCHESTRATOR - All models work like neurons
        self.neural_orchestrator = get_neural_orchestrator(event_bus)
        self.neural_mode_enabled = True  # Enable neural multi-model by default
        
        # Live System References (will be initialized)
        self.live_order_book = None
        self.live_trades_feed = None
        self.live_price_charts = None
        self.live_arbitrage = None
        self.live_sentiment = None
        self.live_risk_manager = None
        self.live_portfolio = None
        self.live_ai_strategies = None
        self.live_meme_scanner = None
        self.live_quantum = None
        self.live_smart_contracts = None
        self.real_exchange_executor = None
        
        # SOTA 2025: Position Monitor for TP/SL enforcement
        self.position_monitor: Optional[PositionMonitor] = None
        
        # SOTA 2025-2026: Coin Accumulation Intelligence - Stack Sats Mode
        self.accumulation_intelligence: Optional[CoinAccumulationIntelligence] = None
        
        # Thoth AI Instance
        self.thoth = None
        self.ollama_available = False
        
        # Autonomous Trading Settings (global compatibility flag)
        self.autonomous_mode = False
        self.max_trade_size_usd = 1000.0  # Maximum single trade size
        self.risk_tolerance = 'medium'  # low, medium, high

        # PREDATOR MODE (24h transition)
        # This is a runtime behavioral switch that makes Thoth more aggressive
        # after the study/learning window, driven by LearningOrchestrator and
        # ContinuousMarketMonitor events.
        self.predator_mode: bool = False
        self.predator_mode_source: Optional[str] = None
        self.predator_mode_since_ts: Optional[float] = None
        self.latest_predator_mode_event: Optional[Dict[str, Any]] = None

        # Per-asset-class autonomous state used by event-driven loops
        self.crypto_autonomous: bool = False
        self.stocks_autonomous: bool = False
        self.crypto_symbols: List[str] = []
        self.stock_symbols: List[str] = []
        self._crypto_task: Optional[asyncio.Task] = None
        self._stocks_task: Optional[asyncio.Task] = None

        self._position_sizer: PositionSizer = PositionSizer()

        # Latest snapshot payloads from backend components (read-only cache)
        self.latest_portfolio_snapshot: Optional[Dict[str, Any]] = None
        self.latest_risk_snapshot: Optional[Dict[str, Any]] = None
        self.latest_arbitrage_snapshot: Optional[Dict[str, Any]] = None
        self.latest_ai_snapshot: Optional[Dict[str, Any]] = None
        self.latest_prediction_snapshot: Optional[Dict[str, Any]] = None
        self.latest_sentiment_snapshot: Optional[Dict[str, Any]] = None
        self.latest_strategy_marketplace_snapshot: Optional[Dict[str, Any]] = None
        self.latest_exchange_health_snapshot: Optional[Dict[str, Any]] = None
        self.latest_stock_broker_health_snapshot: Optional[Dict[str, Any]] = None
        # Profit goal / hub telemetry snapshots so the Ollama brain knows
        # about the global $2T objective and current progress.
        self.latest_profit_goal_snapshot: Optional[Dict[str, Any]] = None
        self.latest_profit_report_snapshot: Optional[Dict[str, Any]] = None
        # KAIG THREE TARGETS — every AI decision must know these
        self.latest_kaig_directive: Optional[Dict[str, Any]] = None
        self.latest_symbol_index: Optional[List[Dict[str, Any]]] = None
        self.symbol_performance: Dict[str, Any] = {}
        self.latest_anomaly_snapshot: Optional[Dict[str, Any]] = None
        # Paper auto-trade orchestrator state so Thoth/Ollama can see
        # simulated performance and readiness when making decisions.
        self.latest_paper_metrics: Optional[Dict[str, Any]] = None
        self.latest_autotrade_readiness: Optional[Dict[str, Any]] = None
        self._auto_trade_started_after_ready: bool = False
        # Learning orchestrator state over 24h multi-source window.
        self.latest_learning_metrics: Optional[Dict[str, Any]] = None
        self.latest_learning_readiness: Optional[Dict[str, Any]] = None
        # Online RL trainer metrics (streaming background Q-learning over
        # paper trading telemetry).
        self.latest_rl_online_metrics: Optional[Dict[str, Any]] = None
        # Latest profit-policy diagnostics (from auto-trade loops and
        # OrderRouter). This exposes reasons why trades would fail the
        # near-100%-win-rate profit gate so Thoth/Ollama can actively work to
        # eliminate those violations.
        self.latest_policy_diagnostics: Optional[Dict[str, Any]] = None
        
        # VISION SYSTEM STATE (Thoth's Eye) - Real webcam data
        self.vision_active: bool = False
        self.vision_url: str = ""
        self.latest_vision_analysis: Optional[Dict[str, Any]] = None
        
        # VR CREATION SYSTEM STATE - Real 3D design collaboration
        self.latest_vr_design_request: Optional[Dict[str, Any]] = None
        self.active_vr_designs: Dict[str, Any] = {}
        self.latest_vr_interaction: Optional[Dict[str, Any]] = None
        self.vr_session_state: Dict[str, Any] = {}
        self.latest_vr_tracking: Optional[Dict[str, Any]] = None
        self.latest_vr_sentience_metrics: Optional[Dict[str, Any]] = None
        self.latest_vr_status: Optional[Dict[str, Any]] = None
        # Recent VR actions/operations (compact telemetry for the brain)
        self.vr_action_history: List[Dict[str, Any]] = []
        self.latest_vr_performance: Optional[Dict[str, Any]] = None
        
        # Register event bus subscriptions if available
        if self.event_bus is not None:
            try:
                self._register_event_subscriptions()
            except Exception as sub_err:
                logger.warning(f"ThothLiveIntegration event subscription failed: {sub_err}")
        
        logger.info("✅ Thoth Live Integration initialized with NEURAL MULTI-MODEL ORCHESTRATION")
    
    def _register_event_subscriptions(self):
        """Subscribe to snapshot streams and AI auto-trade control events."""
        if not self.event_bus:
            return

        # Snapshot streams from backend components
        self.event_bus.subscribe("trading.portfolio.snapshot", self._on_portfolio_snapshot)
        self.event_bus.subscribe("trading.risk.snapshot", self._on_risk_snapshot)
        self.event_bus.subscribe("trading.arbitrage.snapshot", self._on_arbitrage_snapshot)
        self.event_bus.subscribe("trading.ai.snapshot", self._on_ai_snapshot)
        self.event_bus.subscribe("trading.prediction.snapshot", self._on_prediction_snapshot)
        self.event_bus.subscribe("trading.sentiment.snapshot", self._on_sentiment_snapshot)
        self.event_bus.subscribe("trading.strategy_marketplace.snapshot", self._on_strategy_marketplace_snapshot)
        self.event_bus.subscribe("exchange.health.snapshot", self._on_exchange_health_snapshot)
        self.event_bus.subscribe("stock.broker.health.snapshot", self._on_stock_broker_health_snapshot)
        self.event_bus.subscribe("trading.symbol_index", self._on_symbol_index)
        self.event_bus.subscribe("trading.anomaly.snapshot", self._on_anomaly_snapshot)
        # Global profit goal and hub-level profit telemetry so Thoth/Ollama
        # are explicitly aware of the $2T target and current progress.
        self.event_bus.subscribe("trading.intelligence.goal_progress", self._on_trading_goal_progress)
        self.event_bus.subscribe("trading.profit.report", self._on_trading_profit_report)
        # KAIG Intelligence Bridge — THREE TARGETS + rebrand resilience
        self.event_bus.subscribe("kaig.intel.trading.directive", self._on_kaig_trading_directive)
        self.event_bus.subscribe("kaig.ath.update", self._on_kaig_ath_update)
        self.event_bus.subscribe("kaig.identity.changed", self._on_identity_changed)
        # Paper auto-trade orchestrator metrics and readiness for SAFE
        # enablement of live trading.
        self.event_bus.subscribe("autotrade.paper.metrics", self._on_autotrade_paper_metrics)
        self.event_bus.subscribe("autotrade.readiness", self._on_autotrade_readiness)
        # Learning orchestrator metrics/readiness for 24h study window.
        self.event_bus.subscribe("learning.metrics", self._on_learning_metrics)
        self.event_bus.subscribe("learning.readiness", self._on_learning_readiness)
        # Online RL trainer metrics over paper trading telemetry.
        self.event_bus.subscribe("learning.rl_online.metrics", self._on_learning_rl_online_metrics)
        # Profit-policy diagnostics from auto-trade loops and OrderRouter.
        self.event_bus.subscribe("autotrade.policy.diagnostics", self._on_policy_diagnostics)

        # AI auto-trade control events (crypto vs stocks)
        self.event_bus.subscribe("ai.autotrade.crypto.enable", self._on_ai_crypto_enable)
        self.event_bus.subscribe("ai.autotrade.crypto.disable", self._on_ai_crypto_disable)
        self.event_bus.subscribe("ai.autotrade.stocks.enable", self._on_ai_stocks_enable)
        self.event_bus.subscribe("ai.autotrade.stocks.disable", self._on_ai_stocks_disable)
        # High-level orchestration: analyze markets then start auto-trading
        self.event_bus.subscribe("ai.autotrade.analyze_and_start", self._on_ai_analyze_and_start)

        # Live opportunities emitted by GUI-side continuous monitor.
        self.event_bus.subscribe("ollama.live_opportunities", self._on_ollama_live_opportunities)

        # PREDATOR MODE transition broadcast (ContinuousMarketMonitor).
        self.event_bus.subscribe("system.predator_mode_activated", self._on_predator_mode_activated)
        
        # PREDATOR MODE: Complete market analysis request (manual or scheduled)
        self.event_bus.subscribe("ai.predator.analyze_complete_market", self._on_predator_analyze_complete_market)

        # GUI-side complete intelligence analysis payloads.
        self.event_bus.subscribe("ollama.analyze_markets", self._on_ollama_analyze_markets)

        # 24h analysis/study window (analysis only, no live trading).
        self.event_bus.subscribe("ai.analysis.start_24h", self._on_ai_analysis_start_24h)
        
        # SOTA 2025: Order fill events for position monitoring with TP/SL
        self.event_bus.subscribe("trading.order_filled", self._on_order_filled_for_monitoring)
        self.event_bus.subscribe("trading.order_update", self._on_order_update_for_monitoring)
        
        # SOTA 2025-2026: Wallet Intelligence - Accumulation queries from coin intelligence
        self.event_bus.subscribe("thoth.accumulation.query", self._on_accumulation_query)
        self.event_bus.subscribe("wallet.intelligence.portfolio_value", self._on_wallet_portfolio_value)
        
        # VISION SYSTEM (Thoth's Eye) - Real webcam data, no mocks
        self.event_bus.subscribe("vision.stream.status", self._on_vision_status)
        self.event_bus.subscribe("vision.analysis.face", self._on_vision_analysis)
        
        # VR CREATION SYSTEM - Real 3D design collaboration
        self.event_bus.subscribe("vr.design.request", self._on_vr_design_request)
        self.event_bus.subscribe("vr.design.state", self._on_vr_design_state)
        self.event_bus.subscribe("vr.interaction", self._on_vr_interaction)
        self.event_bus.subscribe("vr.session.started", self._on_vr_session_started)
        self.event_bus.subscribe("vr.session.ended", self._on_vr_session_ended)
        self.event_bus.subscribe("vr.tracking.update", self._on_vr_tracking_update)
        # Sentience integration publishes vr.sentience.update with vr_metrics
        self.event_bus.subscribe("vr.sentience.update", self._on_vr_sentience_metrics)
        self.event_bus.subscribe("vr.status", self._on_vr_status)
        self.event_bus.subscribe("vr.performance.update", self._on_vr_performance)
        # High-level VR system events for AI telemetry
        self.event_bus.subscribe("vr.environment_loaded", self._on_vr_environment_loaded)
        self.event_bus.subscribe("vr.settings_reset", self._on_vr_settings_reset)
        self.event_bus.subscribe("vr.mode_active", self._on_vr_mode_active)
        # Wireless connection lifecycle events from VRManager
        self.event_bus.subscribe("vr.wireless.auto_connect.success", self._on_vr_wireless_auto_connect_success)
        self.event_bus.subscribe("vr.wireless.auto_connect.failed", self._on_vr_wireless_auto_connect_failed)
        self.event_bus.subscribe("vr.wireless.auto_pair.success", self._on_vr_wireless_auto_pair_success)
        self.event_bus.subscribe("vr.wireless.auto_pair.failed", self._on_vr_wireless_auto_pair_failed)
        self.event_bus.subscribe("vr.wireless.disconnected", self._on_vr_wireless_disconnected)
        self.event_bus.subscribe("vr.wireless.reconnected", self._on_vr_wireless_reconnected)
        self.event_bus.subscribe("vr.wireless.reconnect_failed", self._on_vr_wireless_reconnect_failed)

    async def initialize_thoth(self):
        """Initialize Ollama-based Thoth AI brain.
        
        MEMORY-SAFE: Neural multi-model orchestration is deferred to first request
        to prevent OOM during startup from loading multiple models simultaneously.
        Uses same WSL-aware URL as BrainRouter (get_ollama_base_url) so Ollama brain
        is used first, then unified flow.
        """
        try:
            from core.ollama_config import get_ollama_base_url
            ollama_base = get_ollama_base_url()
            tags_url = f"{ollama_base.rstrip('/')}/api/tags"
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(tags_url) as response:
                    if response.status == 200:
                        models = await response.json()
                        model_names = [m.get('name', '') for m in models.get('models', [])]
                        logger.info(f"✅ Ollama connected - {len(model_names)} models available")
                        logger.info(f"   🧠 Models: {', '.join(model_names[:5])}{'...' if len(model_names) > 5 else ''}")
                        self.ollama_available = True
                    else:
                        logger.warning("Ollama not responding")
                        self.ollama_available = False
            
            # MEMORY-SAFE: Skip neural orchestrator initialization during startup
            # Neural multi-model orchestration will initialize lazily on first AI request
            # This prevents OOM from loading multiple Ollama models simultaneously with XTTS
            if self.ollama_available:
                logger.info("✅ Thoth AI brain ONLINE with Ollama")
                logger.info("   🧠 Neural multi-model orchestration will activate on first request")
            else:
                logger.warning("Thoth AI running in offline mode")
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Thoth: {e}")
            return False
    
    def connect_all_live_systems(
        self,
        order_book,
        trades_feed,
        price_charts,
        arbitrage,
        sentiment,
        risk_manager,
        portfolio,
        ai_strategies,
        meme_scanner,
        quantum,
        smart_contracts,
        exchange_executor
    ):
        """
        Connect ALL live systems to Thoth AI.
        
        Args:
            order_book: LiveOrderBook instance
            trades_feed: LiveTradesFeed instance
            price_charts: LivePriceCharts instance
            arbitrage: LiveArbitrageScanner instance
            sentiment: LiveSentimentAnalyzer instance
            risk_manager: LiveRiskManager instance
            portfolio: LivePortfolioAnalytics instance
            ai_strategies: LiveAIStrategies instance
            meme_scanner: LiveMemeScanner instance
            quantum: LiveQuantumTrading instance
            smart_contracts: LiveSmartContracts instance
            exchange_executor: RealExchangeExecutor instance
        """
        self.live_order_book = order_book
        self.live_trades_feed = trades_feed
        self.live_price_charts = price_charts
        self.live_arbitrage = arbitrage
        self.live_sentiment = sentiment
        self.live_risk_manager = risk_manager
        self.live_portfolio = portfolio
        self.live_ai_strategies = ai_strategies
        self.live_meme_scanner = meme_scanner
        self.live_quantum = quantum
        self.live_smart_contracts = smart_contracts
        self.real_exchange_executor = exchange_executor
        
        logger.info("✅ Thoth AI connected to ALL live systems:")
        logger.info("   📊 Order Book: LIVE")
        logger.info("   💹 Trades Feed: LIVE")
        logger.info("   📈 Price Charts: LIVE")
        logger.info("   💰 Arbitrage: LIVE")
        logger.info("   📰 Sentiment: LIVE")
        logger.info("   🛡️ Risk Manager: LIVE")
        logger.info("   💼 Portfolio: LIVE")
        logger.info("   🤖 AI Strategies: LIVE")
        logger.info("   🚀 Meme Scanner: LIVE")
        logger.info("   ⚛️ Quantum: LIVE")
        logger.info("   📜 Smart Contracts: LIVE")
        logger.info("   💱 Exchange Executor: LIVE")
    
    async def _on_portfolio_snapshot(self, payload: Dict[str, Any]) -> None:
        self.latest_portfolio_snapshot = payload

    async def _on_risk_snapshot(self, payload: Dict[str, Any]) -> None:
        self.latest_risk_snapshot = payload

    async def _on_arbitrage_snapshot(self, payload: Dict[str, Any]) -> None:
        self.latest_arbitrage_snapshot = payload

    async def _on_ai_snapshot(self, payload: Dict[str, Any]) -> None:
        self.latest_ai_snapshot = payload

    async def _on_prediction_snapshot(self, payload: Dict[str, Any]) -> None:
        self.latest_prediction_snapshot = payload

    async def _on_sentiment_snapshot(self, payload: Dict[str, Any]) -> None:
        self.latest_sentiment_snapshot = payload

    async def _on_strategy_marketplace_snapshot(self, payload: Dict[str, Any]) -> None:
        self.latest_strategy_marketplace_snapshot = payload

    async def _on_exchange_health_snapshot(self, payload: Dict[str, Any]) -> None:
        self.latest_exchange_health_snapshot = payload

    async def _on_stock_broker_health_snapshot(self, payload: Dict[str, Any]) -> None:
        self.latest_stock_broker_health_snapshot = payload

    async def _on_symbol_index(self, payload: Dict[str, Any]) -> None:
        """Cache unified symbol index derived from API-keyed venues.

        Payload shape is expected to be {"symbols": [...]} where each entry
        includes at least symbol, asset_class, venues, popularity.
        """
        try:
            symbols = payload.get("symbols") if isinstance(payload, dict) else None
            if isinstance(symbols, list):
                self.latest_symbol_index = symbols
        except Exception as e:
            logger.error(f"Error handling trading.symbol_index: {e}")

    async def _on_anomaly_snapshot(self, payload: Dict[str, Any]) -> None:
        self.latest_anomaly_snapshot = payload

    async def _on_autotrade_paper_metrics(self, payload: Dict[str, Any]) -> None:
        """Cache paper auto-trade performance metrics and mirror into ai.telemetry.

        Payload is emitted by PaperAutotradeOrchestrator as autotrade.paper.metrics
        and contains equity, win_rate, drawdown, etc. This gives Thoth/Ollama
        full awareness of simulated performance before and during live trading.
        """
        try:
            if not isinstance(payload, dict):
                return
            self.latest_paper_metrics = payload
            if self.event_bus:
                try:
                    metrics = payload
                    self.event_bus.publish(
                        "ai.telemetry",
                        {
                            "event_type": "autotrade.paper.metrics",
                            "success": True,
                            "timestamp": datetime.utcnow().isoformat(),
                            "trade_count": metrics.get("trade_count"),
                            "wins": metrics.get("wins"),
                            "losses": metrics.get("losses"),
                            "win_rate": metrics.get("win_rate"),
                            "net_profit": metrics.get("net_profit"),
                            "max_drawdown": metrics.get("max_drawdown"),
                            "equity": metrics.get("equity"),
                            "elapsed_seconds": metrics.get("elapsed_seconds"),
                        },
                    )
                except Exception as telem_err:
                    logger.error(f"Error publishing ai.telemetry autotrade.paper.metrics: {telem_err}")
        except Exception as e:
            logger.error(f"Error handling autotrade.paper.metrics: {e}")

    async def _on_autotrade_readiness(self, payload: Dict[str, Any]) -> None:
        """Cache autotrade.readiness state and mirror into ai.telemetry.

        States: WARMUP, LEARNING, READY, FAILED. This is used only as
        telemetry/context; TradingTab remains responsible for how it
        presents readiness to the user.
        """
        try:
            if not isinstance(payload, dict):
                return
            self.latest_autotrade_readiness = payload
            state = str(payload.get("state") or "").upper()
            if self.event_bus:
                try:
                    self.event_bus.publish(
                        "ai.telemetry",
                        {
                            "event_type": "autotrade.readiness",
                            "success": True,
                            "timestamp": datetime.utcnow().isoformat(),
                            "state": payload.get("state"),
                            "reason": payload.get("reason"),
                            "elapsed_seconds": payload.get("elapsed_seconds"),
                            "time_remaining_seconds": payload.get("time_remaining_seconds"),
                            "study_duration_target": payload.get("study_duration_target"),
                            "trade_count": (payload.get("metrics") or {}).get("trade_count"),
                            "win_rate": (payload.get("metrics") or {}).get("win_rate"),
                            "max_drawdown": (payload.get("metrics") or {}).get("max_drawdown"),
                        },
                    )
                except Exception as telem_err:
                    logger.error(f"Error publishing ai.telemetry autotrade.readiness: {telem_err}")

                # Auto-start trading once analysis/readiness reports READY.
                if state == "READY" and not self._auto_trade_started_after_ready:
                    self._auto_trade_started_after_ready = True
                    self.event_bus.publish("trading.auto_trade.started", {
                        "source": "autotrade.readiness",
                        "reason": payload.get("reason"),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    self.event_bus.publish("trading.auto.start", {
                        "source": "autotrade.readiness",
                        "reason": payload.get("reason"),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    # Ensure full analyze-and-start orchestration runs once.
                    self.event_bus.publish("ai.autotrade.analyze_and_start", {
                        "source": "autotrade.readiness",
                        "risk_tolerance": self.risk_tolerance,
                        "max_trade_size_usd": self.max_trade_size_usd,
                        "reason": payload.get("reason"),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    self.event_bus.publish("trading.system.readiness", {
                        "state": "READY",
                        "auto_trade_started": True,
                        "analysis_ready": True,
                        "reason": payload.get("reason"),
                        "risk_tolerance": self.risk_tolerance,
                        "max_trade_size_usd": self.max_trade_size_usd,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                elif state != "READY":
                    # Allow a future READY transition to trigger start again.
                    self._auto_trade_started_after_ready = False
                    self.event_bus.publish("trading.system.readiness", {
                        "state": state or "LEARNING",
                        "auto_trade_started": False,
                        "analysis_ready": False,
                        "reason": payload.get("reason"),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
        except Exception as e:
            logger.error(f"Error handling autotrade.readiness: {e}")

    # =========================================================================
    # VISION SYSTEM HANDLERS (Thoth's Eye) - Real webcam data, no mocks
    # =========================================================================
    
    async def _on_vision_status(self, payload: Dict[str, Any]) -> None:
        """Handle vision stream status updates from VisionStreamComponent."""
        try:
            active = payload.get("active", False)
            url = payload.get("url", "")
            error = payload.get("error")
            
            self.vision_active = active
            self.vision_url = url
            
            if error:
                logger.warning(f"👁️ Thoth's Eye error: {error}")
            elif active:
                logger.info(f"👁️ Thoth's Eye ACTIVE - streaming from {url}")
            else:
                logger.info("👁️ Thoth's Eye INACTIVE")
        except Exception as e:
            logger.error(f"Error handling vision.stream.status: {e}")
    
    async def _on_vision_analysis(self, payload: Dict[str, Any]) -> None:
        """Handle face/emotion analysis from VisionAnalysisComponent.
        
        Payload contains:
        - num_faces: int
        - dominant_emotion: str (happy, sad, angry, surprised, etc.)
        - emotions: Dict[str, float] (emotion -> confidence)
        - faces: List[Dict] with box, age, gender, emotion per face
        """
        try:
            num_faces = payload.get("num_faces", 0)
            dominant_emotion = payload.get("dominant_emotion")
            emotions = payload.get("emotions", {})
            
            # Store latest vision analysis for Thoth AI context
            self.latest_vision_analysis = {
                "num_faces": num_faces,
                "dominant_emotion": dominant_emotion,
                "emotions": emotions,
                "timestamp": payload.get("timestamp"),
                "has_deepface": payload.get("has_deepface", False)
            }
            
            if num_faces > 0 and dominant_emotion:
                logger.debug(f"👁️ Thoth sees {num_faces} face(s), emotion: {dominant_emotion}")
        except Exception as e:
            logger.error(f"Error handling vision.analysis.face: {e}")
    
    # =========================================================================
    # VR CREATION SYSTEM HANDLERS - Real 3D design collaboration
    # =========================================================================
    
    async def _on_vr_design_request(self, payload: Dict[str, Any]) -> None:
        """Handle VR design creation requests from user.
        
        This is forwarded to ThothOllamaConnector which generates the design spec.
        """
        try:
            prompt = payload.get("prompt", "")
            source = payload.get("source", "unknown")
            
            logger.info(f"🥽 VR Design Request from {source}: {prompt[:50]}...")
            
            # Store the request for context
            self.latest_vr_design_request = {
                "prompt": prompt,
                "source": source,
                "timestamp": payload.get("timestamp")
            }
            self._record_vr_action("design", "vr.design.request", payload)
            
            # The actual design generation is handled by ThothOllamaConnector
            # which subscribes to vr.design.request and publishes vr.brain.design_spec
        except Exception as e:
            logger.error(f"Error handling vr.design.request: {e}")
    
    async def _on_vr_design_state(self, payload: Dict[str, Any]) -> None:
        """Handle VR design state updates (position, rotation, scale changes)."""
        try:
            design_id = payload.get("design_id")
            spec = payload.get("spec", {})
            
            if design_id:
                self.active_vr_designs = getattr(self, 'active_vr_designs', {})
                self.active_vr_designs[design_id] = {
                    "spec": spec,
                    "name": spec.get("name"),
                    "position": spec.get("position"),
                    "rotation": spec.get("rotation"),
                    "timestamp": payload.get("timestamp")
                }
                logger.debug(f"🥽 VR Design updated: {design_id}")
            self._record_vr_action("design", "vr.design.state", payload)
        except Exception as e:
            logger.error(f"Error handling vr.design.state: {e}")
    
    async def _on_vr_interaction(self, payload: Dict[str, Any]) -> None:
        """Handle VR interaction events (gestures, grabs, voice commands)."""
        try:
            action = payload.get("action")
            device_id = payload.get("device_id")
            object_id = payload.get("object_id")
            
            self.latest_vr_interaction = {
                "action": action,
                "device_id": device_id,
                "object_id": object_id,
                "timestamp": payload.get("timestamp")
            }
            
            if action:
                logger.debug(f" VR Interaction: {action} on {object_id or 'scene'}")
            self._record_vr_action("interaction", "vr.interaction", payload)
        except Exception as e:
            logger.error(f"Error handling vr.interaction: {e}")

    async def _on_vr_session_started(self, payload: Dict[str, Any]) -> None:
        try:
            self.vr_session_state = {
                "active": True,
                "session_id": payload.get("session_id"),
                "environment": payload.get("environment"),
                "started_at": payload.get("start_time") or payload.get("timestamp"),
            }
            self._record_vr_action("session", "vr.session.started", payload)
        except Exception as e:
            logger.error(f"Error handling vr.session.started: {e}")

    async def _on_vr_session_ended(self, payload: Dict[str, Any]) -> None:
        try:
            ended_at = payload.get("end_time") or payload.get("timestamp")
            duration = payload.get("duration")
            if not self.vr_session_state:
                self.vr_session_state = {}
            self.vr_session_state.update(
                {
                    "active": False,
                    "ended_at": ended_at,
                    "duration": duration,
                }
            )
            self._record_vr_action("session", "vr.session.ended", payload)
        except Exception as e:
            logger.error(f"Error handling vr.session.ended: {e}")

    async def _on_vr_tracking_update(self, payload: Dict[str, Any]) -> None:
        try:
            head_data: Dict[str, Any] = {}
            hmd_pose = payload.get("hmd_pose") if isinstance(payload, dict) else None
            if isinstance(hmd_pose, dict):
                head_data["position"] = hmd_pose.get("position")
                head_data["velocity"] = hmd_pose.get("velocity")
                head_data["angular_velocity"] = hmd_pose.get("angular_velocity")
            else:
                head = payload.get("head") if isinstance(payload, dict) else None
                if isinstance(head, dict):
                    head_data["position"] = head.get("position")
                    head_data["rotation"] = head.get("rotation")
            self.latest_vr_tracking = {
                "head": head_data if head_data else None,
                "tracking_quality": payload.get("tracking_quality") if isinstance(payload, dict) else None,
                "timestamp": payload.get("timestamp") if isinstance(payload, dict) else None,
            }
        except Exception as e:
            logger.error(f"Error handling vr.tracking.update: {e}")

    async def _on_vr_sentience_metrics(self, payload: Dict[str, Any]) -> None:
        try:
            # Sentience integration publishes vr.sentience.update with vr_metrics
            metrics = None
            if isinstance(payload, Dict):
                metrics = payload.get("vr_metrics") or payload.get("metrics")
            if isinstance(metrics, dict):
                self.latest_vr_sentience_metrics = metrics
                self._record_vr_action("sentience", "vr.sentience.update", payload)
        except Exception as e:
            logger.error(f"Error handling vr.sentience.update: {e}")

    async def _on_vr_status(self, payload: Dict[str, Any]) -> None:
        try:
            if isinstance(payload, dict):
                self.latest_vr_status = payload
                self._record_vr_action("status", "vr.status", payload)
        except Exception as e:
            logger.error(f"Error handling vr.status: {e}")

    async def _on_vr_performance(self, payload: Dict[str, Any]) -> None:
        """Handle VR performance telemetry updates (fps, frame time, drops)."""
        try:
            if isinstance(payload, dict):
                self.latest_vr_performance = payload
                self._record_vr_action("performance", "vr.performance.update", payload)
        except Exception as e:
            logger.error(f"Error handling vr.performance.update: {e}")

    async def _on_vr_environment_loaded(self, payload: Dict[str, Any]) -> None:
        """Record environment load events for AI context."""
        try:
            self._record_vr_action("environment", "vr.environment_loaded", payload)
        except Exception as e:
            logger.error(f"Error handling vr.environment_loaded: {e}")

    async def _on_vr_settings_reset(self, payload: Dict[str, Any]) -> None:
        """Record VR settings reset events for AI context."""
        try:
            self._record_vr_action("settings", "vr.settings_reset", payload)
        except Exception as e:
            logger.error(f"Error handling vr.settings_reset: {e}")

    async def _on_vr_mode_active(self, payload: Dict[str, Any]) -> None:
        """Record VR mode activation events for AI context."""
        try:
            self._record_vr_action("mode", "vr.mode_active", payload)
        except Exception as e:
            logger.error(f"Error handling vr.mode_active: {e}")

    # Wireless connection lifecycle telemetry
    async def _on_vr_wireless_auto_connect_success(self, payload: Dict[str, Any]) -> None:
        try:
            self._record_vr_action("connection", "vr.wireless.auto_connect.success", payload)
        except Exception as e:
            logger.error(f"Error handling vr.wireless.auto_connect.success: {e}")

    async def _on_vr_wireless_auto_connect_failed(self, payload: Dict[str, Any]) -> None:
        try:
            self._record_vr_action("connection", "vr.wireless.auto_connect.failed", payload)
        except Exception as e:
            logger.error(f"Error handling vr.wireless.auto_connect.failed: {e}")

    async def _on_vr_wireless_auto_pair_success(self, payload: Dict[str, Any]) -> None:
        try:
            self._record_vr_action("connection", "vr.wireless.auto_pair.success", payload)
        except Exception as e:
            logger.error(f"Error handling vr.wireless.auto_pair.success: {e}")

    async def _on_vr_wireless_auto_pair_failed(self, payload: Dict[str, Any]) -> None:
        try:
            self._record_vr_action("connection", "vr.wireless.auto_pair.failed", payload)
        except Exception as e:
            logger.error(f"Error handling vr.wireless.auto_pair.failed: {e}")

    async def _on_vr_wireless_disconnected(self, payload: Dict[str, Any]) -> None:
        try:
            self._record_vr_action("connection", "vr.wireless.disconnected", payload)
        except Exception as e:
            logger.error(f"Error handling vr.wireless.disconnected: {e}")

    async def _on_vr_wireless_reconnected(self, payload: Dict[str, Any]) -> None:
        try:
            self._record_vr_action("connection", "vr.wireless.reconnected", payload)
        except Exception as e:
            logger.error(f"Error handling vr.wireless.reconnected: {e}")

    async def _on_vr_wireless_reconnect_failed(self, payload: Dict[str, Any]) -> None:
        try:
            self._record_vr_action("connection", "vr.wireless.reconnect_failed", payload)
        except Exception as e:
            logger.error(f"Error handling vr.wireless.reconnect_failed: {e}")

    def _record_vr_action(self, category: str, event: str, payload: Dict[str, Any]) -> None:
        """Record a compact VR action entry for AI context.

        This keeps a small rolling history of the most recent VR operations so
        the Ollama brain can reason about what just happened in VR without
        streaming every low-level event.
        """
        try:
            details: Dict[str, Any] = {}
            if isinstance(payload, dict):
                for key in ("session_id", "environment", "action", "device_id", "object_id", "design_id"):
                    if key in payload:
                        details[key] = payload[key]
            ts = None
            if isinstance(payload, dict):
                ts = payload.get("timestamp")
            if not ts:
                ts = datetime.now().isoformat()
            entry: Dict[str, Any] = {
                "category": category,
                "event": event,
                "timestamp": ts,
            }
            if details:
                entry["details"] = details
            self.vr_action_history.append(entry)
            if len(self.vr_action_history) > 50:
                self.vr_action_history = self.vr_action_history[-50:]
        except Exception:
            # Telemetry recording must never break core logic
            pass

    async def _on_ai_analyze_and_start(self, config: Dict[str, Any]) -> None:
        """Orchestrate a full AI analysis pass, then start crypto and stock auto-trading.

        This uses existing discovery and auto-trade loops so that Ollama/Thoth
        can consume all live signals (indicators, sentiment, arbitrage, risk,
        strategy marketplace, performance) before and during trading.

        Expected config keys (all optional):
            - max_trade_size_usd: float safety cap per trade
            - risk_tolerance: "low" | "medium" | "high"
        """
        try:
            max_size = config.get("max_trade_size_usd")
            try:
                if max_size is not None:
                    self.max_trade_size_usd = float(max_size)
            except (TypeError, ValueError):
                pass

            rt = str(config.get("risk_tolerance") or self.risk_tolerance)
            self.risk_tolerance = rt

            # Discover symbol universes from API-keyed venues/brokers. These
            # functions already respect the current exchange/broker health and
            # symbol index derived from configured API keys.
            crypto_symbols: List[str] = []
            stock_symbols: List[str] = []
            try:
                crypto_symbols = await self._discover_crypto_symbols()
            except Exception as e:
                logger.warning(f"Analyze & Auto Trade: crypto symbol discovery failed: {e}")
            try:
                stock_symbols = await self._discover_stock_symbols()
            except Exception as e:
                logger.warning(f"Analyze & Auto Trade: stock symbol discovery failed: {e}")

            # Optional warm-up: run a single analysis on a few representative
            # symbols so Ollama/Thoth sees the full data stack before loops
            # begin emitting trading signals.
            try:
                for sym in crypto_symbols[:3]:
                    await self.thoth_analyze_market(sym)
            except Exception as warm_err:
                logger.warning(f"Analyze & Auto Trade warm-up error: {warm_err}")

            # Publish explicit analysis-ready signal so readiness gating can
            # transition based on completed analysis instead of fixed 24h window.
            if self.event_bus:
                self.event_bus.publish("ai.autotrade.analysis.ready", {
                    "ready": True,
                    "reason": "Full analysis pass completed",
                    "crypto_symbols_analyzed": len(crypto_symbols),
                    "stock_symbols_analyzed": len(stock_symbols),
                    "timestamp": datetime.utcnow().isoformat(),
                })

            # Build a global auto-trading plan across ALL API-keyed venues and
            # publish it so the GUI can display how Thoth/Ollama intends to
            # trade before the loops start.
            try:
                plan = await self._build_global_autotrade_plan(crypto_symbols, stock_symbols)
                if self.event_bus and isinstance(plan, dict):
                    self.event_bus.publish("ai.autotrade.plan.generated", plan)
            except Exception as plan_err:
                logger.error(f"Error building global auto-trade plan: {plan_err}")

            # Delegate to existing per-asset-class enable handlers so the
            # continuous loops (_crypto_autotrade_loop, _stocks_autotrade_loop)
            # can drive real-time decisions and signals.
            await self._on_ai_crypto_enable(
                {
                    "asset_class": "crypto",
                    "symbols": crypto_symbols,
                    "max_trade_size_usd": self.max_trade_size_usd,
                    "risk_tolerance": self.risk_tolerance,
                }
            )

            await self._on_ai_stocks_enable(
                {
                    "asset_class": "stocks",
                    "symbols": stock_symbols,
                    "max_trade_size_usd": self.max_trade_size_usd,
                    "risk_tolerance": self.risk_tolerance,
                }
            )

            logger.info(
                "✅ Analyze & Auto Trade orchestration complete: crypto=%d, stocks=%d",
                len(crypto_symbols),
                len(stock_symbols),
            )
        except Exception as e:
            logger.error(f"Error handling ai.autotrade.analyze_and_start: {e}")

    async def _on_ai_crypto_enable(self, config: Dict[str, Any]) -> None:
        """Enable AI-driven crypto auto-trading based on GUI config."""
        try:
            symbols_cfg = config.get("symbols") or []
            symbols: List[str] = []
            for s in symbols_cfg:
                if isinstance(s, str) and s:
                    symbols.append(s)
            if not symbols:
                # Automatically derive crypto symbol universe from API-keyed
                # exchanges instead of hardcoding pairs.
                symbols = await self._discover_crypto_symbols()
            self.crypto_symbols = symbols

            max_size = config.get("max_trade_size_usd")
            try:
                if max_size is not None:
                    self.max_trade_size_usd = float(max_size)
            except (TypeError, ValueError):
                pass

            rt = str(config.get("risk_tolerance") or self.risk_tolerance)
            self.risk_tolerance = rt

            self.crypto_autonomous = True
            # Ensure global autonomous safety gate is enabled
            self.enable_autonomous_mode(self.max_trade_size_usd, self.risk_tolerance)

            # SOTA 2025: Start Position Monitor for TP/SL enforcement
            if self.position_monitor is None:
                self.position_monitor = get_position_monitor(self.event_bus)
            if not self.position_monitor.is_monitoring:
                asyncio.create_task(self.position_monitor.start_monitoring())
                logger.info("🎯 Position Monitor started - TP/SL enforcement active")

            # SOTA 2025-2026: Start Coin Accumulation Intelligence - Stack Sats Mode
            if self.accumulation_intelligence is None:
                self.accumulation_intelligence = get_coin_accumulation_intelligence(
                    event_bus=self.event_bus,
                    config={
                        'stablecoin_reserve_pct': 40.0,
                        'min_stable_usd': 100.0,
                        'max_single_buy_pct': 10.0,
                        'auto_execute': False,  # Manual approval - safety first
                    }
                )
            if not self.accumulation_intelligence.is_running:
                asyncio.create_task(self.accumulation_intelligence.start())
                logger.info("🪙 Coin Accumulation Intelligence started - Stack Sats Mode ACTIVE")

            # Start or restart crypto loop
            if self._crypto_task is None or self._crypto_task.done():
                self._crypto_task = asyncio.create_task(self._crypto_autotrade_loop())

            logger.info("✅ AI crypto auto-trade ENABLED for symbols: %s", ", ".join(self.crypto_symbols))
        except Exception as e:
            logger.error(f"Error handling ai.autotrade.crypto.enable: {e}")

    async def _on_ai_crypto_disable(self, _: Dict[str, Any]) -> None:
        """Disable AI-driven crypto auto-trading."""
        try:
            self.crypto_autonomous = False
            if self._crypto_task is not None:
                self._crypto_task.cancel()
            self._crypto_task = None
            logger.info("🛑 AI crypto auto-trade DISABLED")

            if not self.stocks_autonomous:
                self.disable_autonomous_mode()
        except Exception as e:
            logger.error(f"Error handling ai.autotrade.crypto.disable: {e}")

    async def _on_ai_stocks_enable(self, config: Dict[str, Any]) -> None:
        """Enable AI-driven stock auto-trading based on GUI config."""
        try:
            symbols_cfg = config.get("symbols") or []
            symbols: List[str] = []
            for s in symbols_cfg:
                if isinstance(s, str) and s:
                    symbols.append(s)
            if not symbols:
                # Automatically derive stock symbol universe from
                # API-keyed brokers instead of defaulting to a single
                # hardcoded ticker.
                symbols = await self._discover_stock_symbols()
            self.stock_symbols = symbols

            max_size = config.get("max_trade_size_usd")
            try:
                if max_size is not None:
                    self.max_trade_size_usd = float(max_size)
            except (TypeError, ValueError):
                pass

            self.stocks_autonomous = True
            # Ensure global autonomous mode is on when any asset-class is active
            self.enable_autonomous_mode(self.max_trade_size_usd, self.risk_tolerance)

            # SOTA 2025: Start Position Monitor for TP/SL enforcement
            if self.position_monitor is None:
                self.position_monitor = get_position_monitor(self.event_bus)
            if not self.position_monitor.is_monitoring:
                asyncio.create_task(self.position_monitor.start_monitoring())
                logger.info("🎯 Position Monitor started - TP/SL enforcement active")

            # SOTA 2025-2026: Start Coin Accumulation Intelligence - Stack Sats Mode
            if self.accumulation_intelligence is None:
                self.accumulation_intelligence = get_coin_accumulation_intelligence(
                    event_bus=self.event_bus,
                    config={
                        'stablecoin_reserve_pct': 40.0,
                        'min_stable_usd': 100.0,
                        'max_single_buy_pct': 10.0,
                        'auto_execute': False,
                    }
                )
            if not self.accumulation_intelligence.is_running:
                asyncio.create_task(self.accumulation_intelligence.start())
                logger.info("🪙 Coin Accumulation Intelligence started - Stack Sats Mode ACTIVE")

            if self._stocks_task is None or self._stocks_task.done():
                self._stocks_task = asyncio.create_task(self._stocks_autotrade_loop())

            logger.info("✅ AI stocks auto-trade ENABLED for symbols: %s", ", ".join(self.stock_symbols))
        except Exception as e:
            logger.error(f"Error handling ai.autotrade.stocks.enable: {e}")

    async def _on_ai_stocks_disable(self, _: Dict[str, Any]) -> None:
        """Disable AI-driven stock auto-trading."""
        try:
            self.stocks_autonomous = False
            if self._stocks_task is not None:
                self._stocks_task.cancel()
            self._stocks_task = None
            logger.info("🛑 AI stocks auto-trade DISABLED")

            if not self.crypto_autonomous:
                self.disable_autonomous_mode()
        except Exception as e:
            logger.error(f"Error handling ai.autotrade.stocks.disable: {e}")

    async def _on_order_filled_for_monitoring(self, data: Dict[str, Any]) -> None:
        """SOTA 2025: Handle order fills to create monitored positions with TP/SL.
        
        When an entry order is filled, add the position to PositionMonitor
        so TP/SL levels are actively enforced.
        """
        try:
            if self.position_monitor is None:
                return
            
            symbol = data.get('symbol')
            if not symbol:
                return
            
            side_raw = str(data.get('side') or '').lower()
            if side_raw in ('buy', 'long'):
                pos_side = 'long'
            elif side_raw in ('sell', 'short'):
                pos_side = 'short'
            else:
                return  # Not a position-opening fill
            
            # Extract fill details
            entry_price = float(data.get('price') or data.get('filled_price') or 0)
            quantity = float(data.get('quantity') or data.get('filled') or 0)
            
            if entry_price <= 0 or quantity <= 0:
                return
            
            # Get TP/SL from fill data (if included) or calculate
            take_profit = data.get('take_profit_price')
            stop_loss = data.get('stop_loss_price')
            trailing_stop_pct = data.get('trailing_stop_pct')
            
            # If no TP/SL in fill data, calculate from current settings
            if take_profit is None or stop_loss is None:
                asset_class = str(data.get('asset_class') or 'crypto').lower()
                tp_sl = self._calculate_tp_sl_prices(entry_price, pos_side, asset_class)
                take_profit = take_profit or tp_sl.get('take_profit')
                stop_loss = stop_loss or tp_sl.get('stop_loss')
                trailing_stop_pct = trailing_stop_pct or tp_sl.get('trailing_stop_pct')
            
            # Add position to monitor
            await self.position_monitor.add_position(
                symbol=str(symbol),
                side=pos_side,
                entry_price=entry_price,
                quantity=quantity,
                take_profit=float(take_profit) if take_profit else None,
                stop_loss=float(stop_loss) if stop_loss else None,
                trailing_stop_pct=float(trailing_stop_pct) if trailing_stop_pct else None,
                venue=str(data.get('venue') or data.get('exchange') or 'unknown'),
                strategy=str(data.get('strategy') or data.get('source') or 'thoth_ai'),
                metadata={'order_id': data.get('order_id'), 'source': data.get('source')},
            )
            
            logger.info(
                f"📊 Position added to monitor: {symbol} {pos_side.upper()} @ ${entry_price:,.4f} | "
                f"TP: ${take_profit or 0:,.4f} | SL: ${stop_loss or 0:,.4f}"
            )
            
        except Exception as e:
            logger.error(f"Error handling order fill for monitoring: {e}")

    async def _on_order_update_for_monitoring(self, data: Dict[str, Any]) -> None:
        """Handle order updates - delegate to fill handler if status is filled."""
        try:
            status = str(data.get('status') or '').lower()
            if status == 'filled':
                await self._on_order_filled_for_monitoring(data)
        except Exception as e:
            logger.error(f"Error handling order update for monitoring: {e}")

    async def _on_accumulation_query(self, data: Dict[str, Any]) -> None:
        """SOTA 2025-2026: Handle accumulation queries from Coin Intelligence.
        
        Uses Ollama/Thoth brain to make smart accumulation decisions.
        """
        try:
            symbol = str(data.get('symbol') or '').upper()
            current_price = float(data.get('current_price') or 0)
            dip_pct = float(data.get('dip_percentage') or 0)
            available_funds = float(data.get('available_funds') or 0)
            question = data.get('question') or ''
            
            if not symbol or current_price <= 0:
                return
            
            logger.info(f"🧠 Thoth analyzing accumulation opportunity for {symbol} (dip: {dip_pct:.1f}%)")
            
            # Use Ollama if available to analyze the opportunity
            recommendation = 'hold'
            confidence = 50.0
            reasoning = ''
            
            if self.ollama_available and self.thoth:
                try:
                    # Build analysis prompt
                    prompt = (
                        f"Analyze this crypto accumulation opportunity:\n"
                        f"- Coin: {symbol}\n"
                        f"- Current Price: ${current_price:,.2f}\n"
                        f"- Price Dip: {dip_pct:.1f}% from 24h high\n"
                        f"- Available Funds: ${available_funds:,.2f}\n\n"
                        f"Question: {question}\n\n"
                        f"Respond with: ACCUMULATE or HOLD, confidence (0-100), and brief reasoning."
                    )
                    
                    # Query Thoth brain
                    response = await self._query_ollama_simple(prompt)
                    if response:
                        response_lower = response.lower()
                        if 'accumulate' in response_lower or 'buy' in response_lower:
                            recommendation = 'accumulate'
                            confidence = 75.0 + min(dip_pct, 15.0)  # Higher dip = higher confidence
                        reasoning = response[:200]  # Truncate reasoning
                        
                except Exception as ollama_err:
                    logger.debug(f"Ollama query failed, using heuristics: {ollama_err}")
            
            # Fallback heuristics if Ollama unavailable
            if recommendation == 'hold' and dip_pct >= 5.0:
                # Simple heuristic: buy if dip is significant
                if dip_pct >= 10.0:
                    recommendation = 'accumulate'
                    confidence = 80.0
                    reasoning = f"{symbol} has dipped {dip_pct:.1f}% - good accumulation opportunity"
                elif dip_pct >= 7.0:
                    recommendation = 'accumulate'
                    confidence = 70.0
                    reasoning = f"{symbol} showing moderate dip of {dip_pct:.1f}%"
                elif dip_pct >= 5.0 and available_funds >= 500:
                    recommendation = 'accumulate'
                    confidence = 60.0
                    reasoning = f"Small dip but sufficient funds available"
            
            # Publish response back to accumulation intelligence
            if self.event_bus:
                self.event_bus.publish('thoth.accumulation.response', {
                    'type': 'accumulation_decision',
                    'symbol': symbol,
                    'recommendation': recommendation,
                    'confidence': confidence,
                    'reasoning': reasoning,
                    'current_price': current_price,
                    'dip_pct': dip_pct,
                    'timestamp': datetime.now().isoformat(),
                })
                
                # Also publish to ai.telemetry
                self.event_bus.publish('ai.telemetry', {
                    'event_type': 'thoth_ai.accumulation_decision',
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'recommendation': recommendation,
                        'confidence': confidence,
                        'dip_pct': dip_pct,
                    },
                    'timestamp': datetime.now().isoformat(),
                })
            
            logger.info(f"🎯 Thoth recommendation for {symbol}: {recommendation.upper()} (conf: {confidence:.1f}%)")
            
        except Exception as e:
            logger.error(f"Error handling accumulation query: {e}")

    async def _on_wallet_portfolio_value(self, data: Dict[str, Any]) -> None:
        """Handle wallet intelligence portfolio value updates for profit goal tracking."""
        try:
            total_usd = float(data.get('total_usd') or 0)
            stablecoin_reserve = float(data.get('stablecoin_reserve') or 0)
            utility_value = float(data.get('utility_coins_value') or 0)
            coins_owned = data.get('coins_owned') or {}
            
            # Publish to ai.telemetry for Thoth AI Tab visibility
            if self.event_bus and total_usd > 0:
                self.event_bus.publish('ai.telemetry', {
                    'event_type': 'wallet_intelligence.portfolio_value',
                    'success': True,
                    'data': {
                        'total_usd': total_usd,
                        'stablecoin_reserve': stablecoin_reserve,
                        'utility_coins_value': utility_value,
                        'coin_count': len(coins_owned),
                    },
                    'timestamp': datetime.now().isoformat(),
                })
            
            logger.debug(f"💰 Wallet Intelligence Portfolio: ${total_usd:,.2f} (Stable: ${stablecoin_reserve:,.2f}, Utility: ${utility_value:,.2f})")
            
        except Exception as e:
            logger.debug(f"Error handling wallet portfolio value: {e}")

    async def _query_ollama_simple(self, prompt: str) -> Optional[str]:
        """Simple Ollama query for accumulation decisions."""
        try:
            if not self.ollama_available:
                return None
            
            import os
            try:
                from core.ollama_gateway import orchestrator
                _acc_model = orchestrator.get_model_for_task("trading")
            except ImportError:
                _acc_model = self.current_model or "cogito:latest"
            try:
                from core.ollama_gateway import get_ollama_url
                base = get_ollama_url()
            except ImportError:
                base = "http://localhost:11434"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{base}/api/generate',
                    json={
                        'model': _acc_model,
                        'prompt': prompt,
                        'stream': False,
                        'keep_alive': -1,
                        'options': {'temperature': 0.3, 'num_predict': 150, 'num_gpu': 999}
                    },
                    timeout=aiohttp.ClientTimeout(total=None, sock_read=120)
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get('response', '')
        except Exception:
            pass
        return None

    async def _maybe_publish_ai_snapshot(self, symbol: str, signals: List[Any]) -> None:
        """Publish a streaming AI snapshot for TradingTab using REAL data.

        Snapshot shape matches TradingTab._handle_ai_snapshot expectations and
        is derived strictly from live OHLCV data (LivePriceCharts) and the
        AI signals produced by LiveAIStrategies.
        """

        try:
            if self.event_bus is None or self.live_price_charts is None:
                return

            # Ensure we have recent OHLCV data in the charts component.
            chart_data = self.live_price_charts.get_chart_data(symbol)
            if not chart_data:
                try:
                    await self.live_price_charts.fetch_ohlcv(symbol, "1m", 120)
                    chart_data = self.live_price_charts.get_chart_data(symbol)
                except Exception as fetch_err:
                    logger.error(f"AI snapshot: failed to fetch OHLCV for {symbol}: {fetch_err}")
                    return

            if not chart_data or len(chart_data) < 4:
                return

            closes = np.array([float(c[4]) for c in chart_data], dtype=float)
            if closes.size < 2:
                return

            window_size = int(closes.size)
            latest_price = float(closes[-1])
            if latest_price <= 0:
                return

            # Compute step-wise percentage returns over the last ~10 candles.
            tail = closes[-12:] if closes.size >= 12 else closes
            if tail.size >= 2:
                step_returns = np.diff(tail) / tail[:-1] * 100.0
            else:
                step_returns = np.array([], dtype=float)

            def _pct_ret(steps: int) -> Optional[float]:
                if closes.size <= steps:
                    return None
                try:
                    return float((closes[-1] / closes[-(steps + 1)] - 1.0) * 100.0)
                except Exception:
                    return None

            ret_1 = _pct_ret(1)
            ret_5 = _pct_ret(5)
            ret_10 = _pct_ret(10)

            volatility_abs = float(np.mean(np.abs(step_returns))) if step_returns.size else 0.0

            features: Dict[str, Any] = {
                "return_1": ret_1,
                "return_5": ret_5,
                "return_10": ret_10,
                "volatility_abs": volatility_abs,
            }

            # Use first AISignal as ensemble summary for signal/confidence.
            signal_type = "hold"
            confidence = 0.0
            if signals:
                sig = signals[0]
                try:
                    signal_type = str(getattr(sig, "signal_type", "hold"))
                    confidence = float(getattr(sig, "confidence", 0.0))
                except Exception:
                    pass

            payload = {
                "symbol": symbol,
                "latest_price": latest_price,
                "window_size": window_size,
                "features": features,
                "signal": signal_type,
                "confidence": confidence,
            }

            self.latest_ai_snapshot = payload
            try:
                self.event_bus.publish("trading.ai.snapshot", payload)
            except Exception as pub_err:
                logger.error(f"Error publishing trading.ai.snapshot: {pub_err}")
        except Exception as e:
            logger.error(f"Error building AI snapshot: {e}")

    async def thoth_analyze_market(self, symbol: str) -> Dict[str, Any]:
        """
        Thoth AI analyzes market using ALL live data sources.
        
        Args:
            symbol: Trading pair to analyze
            
        Returns:
            Comprehensive market analysis
        """
        try:
            analysis = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'data_sources': {}
            }
            
            # 1. Get live order book data
            if self.live_order_book:
                order_book = self.live_order_book.get_order_book(symbol)
                analysis['data_sources']['order_book'] = {
                    'best_bid': self.live_order_book.get_best_bid(symbol),
                    'best_ask': self.live_order_book.get_best_ask(symbol),
                    'spread': self.live_order_book.get_spread(symbol)
                }
            
            # 2. Get recent trades
            if self.live_trades_feed:
                recent_trades = self.live_trades_feed.get_recent_trades(symbol, 20)
                analysis['data_sources']['recent_trades'] = {
                    'count': len(recent_trades),
                    'last_price': self.live_trades_feed.get_last_price(symbol),
                    'volume_24h': self.live_trades_feed.get_volume_24h(symbol)
                }
            
            # 3. Get technical indicators
            if self.live_price_charts:
                indicators = self.live_price_charts.calculate_indicators(symbol)
                analysis['data_sources']['technical_indicators'] = indicators
            
            # 4. Get sentiment analysis
            if self.live_sentiment:
                sentiment_data = await self.live_sentiment.analyze_sentiment(symbol.split('/')[0])
                analysis['data_sources']['sentiment'] = {
                    'overall': sentiment_data.overall_sentiment,
                    'score': sentiment_data.sentiment_score,
                    'confidence': sentiment_data.confidence
                }
            
            # 5. Get AI predictions
            if self.live_ai_strategies:
                signals = await self.live_ai_strategies.generate_signals([symbol])
                if signals:
                    analysis['data_sources']['ai_prediction'] = {
                        'signal': signals[0].signal_type,
                        'confidence': signals[0].confidence,
                        'predicted_change': signals[0].predicted_change
                    }

                    # Emit a streaming AI snapshot for TradingTab using the
                    # same REAL features and AISignal outputs.
                    await self._maybe_publish_ai_snapshot(symbol, signals)
            
            # 6. Get quantum analysis
            if self.live_quantum:
                quantum_signals = await self.live_quantum.generate_quantum_signals([symbol])
                if quantum_signals:
                    analysis['data_sources']['quantum'] = {
                        'signal': quantum_signals[0].signal_type,
                        'quantum_score': quantum_signals[0].quantum_score,
                        'entanglement': quantum_signals[0].entanglement_measure
                    }
            
            # 7. Check for arbitrage opportunities
            if self.live_arbitrage:
                arb_opportunities = await self.live_arbitrage.scan_arbitrage([symbol])
                analysis['data_sources']['arbitrage'] = {
                    'opportunities': len(arb_opportunities),
                    'best_profit': arb_opportunities[0].profit_percent if arb_opportunities else 0
                }
            
            # 8. Get risk metrics
            if self.live_risk_manager:
                risk_metrics = await self.live_risk_manager.calculate_risk_metrics()
                analysis['data_sources']['risk'] = {
                    'portfolio_value': risk_metrics.portfolio_value,
                    'risk_score': risk_metrics.risk_score,
                    'leverage': risk_metrics.leverage_ratio
                }

            # 9. Attach latest cached snapshots from backend components
            if self.latest_portfolio_snapshot is not None:
                analysis['data_sources']['portfolio_snapshot'] = self.latest_portfolio_snapshot
            if self.latest_risk_snapshot is not None:
                analysis['data_sources']['risk_snapshot_latest'] = self.latest_risk_snapshot
            if self.latest_arbitrage_snapshot is not None:
                analysis['data_sources']['arbitrage_snapshot_latest'] = self.latest_arbitrage_snapshot
            if self.latest_ai_snapshot is not None:
                analysis['data_sources']['ai_stream_snapshot'] = self.latest_ai_snapshot
            if self.latest_prediction_snapshot is not None:
                analysis['data_sources']['prediction_snapshot'] = self.latest_prediction_snapshot
            if self.latest_sentiment_snapshot is not None:
                analysis['data_sources']['sentiment_snapshot'] = self.latest_sentiment_snapshot
            if self.latest_exchange_health_snapshot is not None:
                analysis['data_sources']['exchange_health_snapshot'] = self.latest_exchange_health_snapshot
            if self.latest_stock_broker_health_snapshot is not None:
                analysis['data_sources']['stock_broker_health_snapshot'] = self.latest_stock_broker_health_snapshot

            # Attach paper auto-trade orchestrator telemetry so Thoth/Ollama
            # can reason about simulated performance and readiness when
            # generating trading decisions.
            if self.latest_paper_metrics is not None:
                analysis['data_sources']['paper_autotrade_metrics'] = self.latest_paper_metrics
            if self.latest_autotrade_readiness is not None:
                analysis['data_sources']['autotrade_readiness'] = self.latest_autotrade_readiness
            if self.latest_learning_metrics is not None:
                analysis['data_sources']['learning_metrics'] = self.latest_learning_metrics
            if self.latest_learning_readiness is not None:
                analysis['data_sources']['learning_readiness'] = self.latest_learning_readiness
            if self.latest_rl_online_metrics is not None:
                analysis['data_sources']['rl_online_metrics'] = self.latest_rl_online_metrics

            # 10. Attach latest profit-policy diagnostics so Thoth/Ollama can
            # see precisely why recent trades would fail the
            # profit-focused policy (global_not_eligible, strategy_not_enabled,
            # size_too_large, etc.) and adapt behavior to eliminate these
            # violations while maintaining profitability.
            if self.latest_policy_diagnostics is not None:
                try:
                    diag = self.latest_policy_diagnostics
                    diag_sym = str(diag.get('symbol') or diag.get('asset_symbol') or '').upper()
                    if not diag_sym or diag_sym == symbol.upper():
                        analysis['data_sources']['policy_diagnostics'] = diag
                except Exception as diag_err:
                    logger.error(f"Error attaching policy diagnostics for {symbol}: {diag_err}")

            # 11. Attach global profit goal telemetry so the Ollama brain sees
            # the $2T target, current profit, progress percentage, and hub
            # win-rate whenever it analyzes any symbol.
            try:
                goal_src = self.latest_profit_goal_snapshot or {}
                report_src = self.latest_profit_report_snapshot or {}

                # Prefer TradingIntelligence goal progress when available.
                target_usd = None
                current_usd = None
                progress_pct = None

                if isinstance(goal_src, dict) and goal_src:
                    target_usd = goal_src.get("target_usd")
                    current_usd = goal_src.get("current_profit_usd")
                    progress_pct = goal_src.get("progress_percent")
                if (target_usd is None or current_usd is None or progress_pct is None) and isinstance(report_src, dict) and report_src:
                    # Fallback to TradingHub profit report fields
                    if target_usd is None:
                        target_usd = report_src.get("profit_target")
                    if current_usd is None:
                        current_usd = report_src.get("current_profit")
                    if progress_pct is None:
                        progress_pct = report_src.get("progress_percentage")

                hub_win_rate = None
                try:
                    perf = report_src.get("performance_metrics") if isinstance(report_src, dict) else None
                    if isinstance(perf, dict):
                        hub_win_rate = perf.get("win_rate")
                except Exception:
                    hub_win_rate = None

                if target_usd is not None or current_usd is not None or progress_pct is not None or hub_win_rate is not None:
                    analysis['data_sources']['profit_goal'] = {
                        "target_usd": target_usd,
                        "current_profit_usd": current_usd,
                        "progress_percent": progress_pct,
                        "hub_win_rate": hub_win_rate,
                        "source_events": {
                            "trading_intelligence_goal_progress": bool(goal_src),
                            "trading_profit_report": bool(report_src),
                        },
                    }
            except Exception as goal_err:
                logger.error(f"Error attaching profit goal telemetry to analysis: {goal_err}")

            # 13. KAIG THREE TARGETS — every Ollama analysis must carry these
            if self.latest_kaig_directive is not None:
                try:
                    kd = self.latest_kaig_directive
                    floor = kd.get("kaig_survival_floor", {})
                    pf = kd.get("kaig_price_floor", {})
                    analysis['data_sources']['kaig_targets'] = {
                        "survival_floor": {
                            "required_realized_gains_usd": floor.get("required_realized_gains_usd", 26000),
                            "kaig_treasury_target_usd": floor.get("kaig_treasury_target_usd", 13000),
                            "survival_met": floor.get("survival_met", False),
                            "urgency": floor.get("urgency", "existential"),
                        },
                        "kaig_price_floor": {
                            "current_ath_coin": pf.get("current_ath_coin", "BTC"),
                            "current_ath_price_usd": pf.get("current_ath_price_usd", 125835.92),
                            "kaig_must_exceed_usd": pf.get("kaig_must_exceed_usd", 125835.93),
                        },
                        "ultimate_profit_target_usd": kd.get("ultimate_profit_target_usd", 2_000_000_000_000),
                        "profit_total_usd": kd.get("profit_total_usd", 0),
                        "buyback_rate": kd.get("buyback_rate", 0.50),
                        "context_summary": self._get_kaig_context_for_prompt(),
                    }
                except Exception as kaig_err:
                    logger.error(f"Error attaching KAIG targets to analysis: {kaig_err}")

            # 10. Attach performance-aware views for RL-style biasing
            symbol_perf_view = self._build_symbol_performance_view(symbol, asset_class="crypto")
            if symbol_perf_view is not None:
                analysis['data_sources']['symbol_performance'] = symbol_perf_view

            # 12. Attach GUI-side complete intelligence analysis and live opportunities
            # These are populated by the continuous monitor and COMPLETE_INTELLIGENCE analysis
            gui_analysis = getattr(self, 'latest_gui_market_analysis', None)
            if gui_analysis is not None:
                analysis['data_sources']['gui_complete_intelligence'] = gui_analysis
            
            live_opps = getattr(self, 'latest_live_opportunities', None)
            if live_opps is not None and isinstance(live_opps, list) and len(live_opps) > 0:
                analysis['data_sources']['continuous_monitor_opportunities'] = live_opps

            if self.latest_anomaly_snapshot is not None:
                try:
                    symbols = self.latest_anomaly_snapshot.get('symbols') if isinstance(self.latest_anomaly_snapshot, dict) else None
                    if isinstance(symbols, list):
                        for entry in symbols:
                            if isinstance(entry, dict) and entry.get('symbol') == symbol:
                                analysis['data_sources']['anomaly_snapshot'] = entry
                                break
                except Exception as e:
                    logger.error(f"Error attaching anomaly snapshot for {symbol}: {e}")

            strategy_view = self._build_strategy_marketplace_view()
            if strategy_view is not None:
                analysis['data_sources']['strategy_marketplace'] = strategy_view

            # 11. Thoth AI synthesis using NEURAL MULTI-MODEL ORCHESTRATION
            if self.ollama_available:
                if self.neural_mode_enabled:
                    # Use ALL models simultaneously like neurons
                    thoth_decision = await self._query_neural_brain(analysis)
                else:
                    # Fallback to single model
                    thoth_decision = await self._query_ollama_brain(analysis)
                analysis['thoth_decision'] = thoth_decision
            else:
                analysis['thoth_decision'] = self._fallback_decision(analysis)
            
            logger.info(f"✅ Thoth analyzed {symbol}: {analysis['thoth_decision']['action']}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in Thoth market analysis: {e}")
            return {'error': str(e)}

    def _on_trading_goal_progress(self, payload: Dict[str, Any]) -> None:
        """Handle trading.intelligence.goal_progress telemetry.

        This event is emitted by TradingIntelligence enhancements and carries
        cumulative profit in USD, the ultimate_profit_target_usd (2T USD), and
        a goal progress percentage. We cache the latest snapshot so
        thoth_analyze_market can inject it into the Ollama analysis context.
        """
        try:
            if not isinstance(payload, dict):
                return
            self.latest_profit_goal_snapshot = payload
            # Mirror goal progress into ai.telemetry so Thoth AI Tab and
            # external observability tools can see the $2T target and
            # current progress alongside request/response events.
            if self.event_bus:
                try:
                    self.event_bus.publish(
                        "ai.telemetry",
                        {
                            "event_type": "thoth_ai.profit_goal",
                            "success": True,
                            "timestamp": datetime.utcnow().isoformat(),
                            "source": "trading_intelligence.goal_progress",
                            "target_usd": payload.get("target_usd"),
                            "current_profit_usd": payload.get("current_profit_usd"),
                            "progress_percent": payload.get("progress_percent"),
                        },
                    )
                except Exception as telem_err:  # noqa: BLE001
                    logger.error(
                        f"Error publishing ai.telemetry profit_goal from goal_progress: {telem_err}"
                    )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error handling trading.intelligence.goal_progress: {e}")

    def _on_trading_profit_report(self, payload: Dict[str, Any]) -> None:
        """Handle trading.profit.report telemetry from TradingHub.

        The TradingHub periodically publishes a consolidated profit report with
        current_profit, profit_target (2T USD), progress_percentage and hub
        performance_metrics including win_rate. We cache the latest report so
        Thoth/Ollama can see global progress and hub win-rate.
        """
        try:
            if not isinstance(payload, dict):
                return
            self.latest_profit_report_snapshot = payload
            # Mirror hub-level profit telemetry into ai.telemetry so the
            # Thoth AI tab and monitoring tools see global progress and
            # win-rate over time.
            if self.event_bus:
                try:
                    perf = payload.get("performance_metrics")
                    hub_win_rate = None
                    if isinstance(perf, dict):
                        hub_win_rate = perf.get("win_rate")

                    self.event_bus.publish(
                        "ai.telemetry",
                        {
                            "event_type": "thoth_ai.profit_goal",
                            "success": True,
                            "timestamp": datetime.utcnow().isoformat(),
                            "source": "trading_hub.profit_report",
                            "target_usd": payload.get("profit_target"),
                            "current_profit_usd": payload.get("current_profit"),
                            "progress_percent": payload.get("progress_percentage"),
                            "hub_win_rate": hub_win_rate,
                        },
                    )
                except Exception as telem_err:  # noqa: BLE001
                    logger.error(
                        f"Error publishing ai.telemetry profit_goal from profit_report: {telem_err}"
                    )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error handling trading.profit.report: {e}")

    def _on_kaig_trading_directive(self, payload: Dict[str, Any]) -> None:
        """Handle KAIG intelligence bridge trading directive — THREE TARGETS.

        Every Ollama/Thoth AI decision must know:
        1. SURVIVAL FLOOR: $26K realized → $13K treasury (existential, FIRST)
        2. KAIG PRICE FLOOR: 1 KAIG > highest crypto ATH ever (live-monitored)
        3. ULTIMATE TARGET: $2T (aspirational, always pursue)
        """
        try:
            if not isinstance(payload, dict):
                return
            self.latest_kaig_directive = payload
            logger.info("ThothLiveIntegration: KAIG directive received — 3 targets loaded")
        except Exception as e:
            logger.error(f"Error handling kaig.intel.trading.directive: {e}")

    def _on_kaig_ath_update(self, payload: Dict[str, Any]) -> None:
        """Handle new crypto ATH detection — KAIG price floor raised."""
        try:
            if not isinstance(payload, dict):
                return
            new_coin = payload.get("new_ath_coin", "")
            new_price = payload.get("new_ath_price", 0)
            logger.warning(
                "ThothLiveIntegration: NEW ATH — %s at $%s. KAIG price floor raised.",
                new_coin, f"{new_price:,.2f}")
            # Update directive if cached
            if self.latest_kaig_directive:
                self.latest_kaig_directive["kaig_price_floor"] = {
                    "current_ath_coin": new_coin,
                    "current_ath_price_usd": new_price,
                    "kaig_must_exceed_usd": payload.get("kaig_price_floor", new_price + 0.01),
                    "live_monitored": True,
                }
        except Exception as e:
            logger.error(f"Error handling kaig.ath.update: {e}")

    def _on_identity_changed(self, payload: Dict[str, Any]) -> None:
        """Handle token rebrand — all Thoth/Ollama AI context updated automatically.
        All user balances preserved. Tracked by wallet address, not token name. Zero loss."""
        if isinstance(payload, dict):
            logger.warning(
                "ThothLiveIntegration: TOKEN REBRANDED %s → %s. "
                "AI context updated. All user funds preserved.",
                payload.get("old_ticker", "?"),
                payload.get("new_ticker", "?"))

    def _get_kaig_context_for_prompt(self) -> str:
        """Build KAIG targets context string for injection into Ollama prompts."""
        d = self.latest_kaig_directive
        if not d or not isinstance(d, dict):
            return (
                "KAIG TARGETS: 1) $26K survival floor (existential) "
                "2) 1 KAIG > $125,835 (highest crypto ATH) "
                "3) $2T ultimate target. 50% profits → KAIG buyback."
            )
        floor = d.get("kaig_survival_floor", {})
        pf = d.get("kaig_price_floor", {})
        survival_met = floor.get("survival_met", False)
        return (
            f"KAIG TARGETS: "
            f"1) Survival: ${floor.get('required_realized_gains_usd', 26000):,.0f} realized "
            f"({'MET' if survival_met else 'NOT MET — PRIORITY'}) "
            f"2) 1 KAIG > ${pf.get('current_ath_price_usd', 125835.92):,.2f} "
            f"({pf.get('current_ath_coin', 'BTC')} ATH, live) "
            f"3) $2T ultimate. "
            f"Profit: ${d.get('profit_total_usd', 0):,.2f}. 50% → KAIG buyback."
        )

    def _on_learning_metrics(self, payload: Dict[str, Any]) -> None:
        """Handle learning.metrics snapshots from LearningOrchestrator.

        We cache the latest metrics and mirror a compact view into ai.telemetry
        so Thoth AI Tab and external observability tools can track learning
        coverage and density over time.
        """
        try:
            if not isinstance(payload, dict):
                return
            self.latest_learning_metrics = payload
            if self.event_bus:
                try:
                    self.event_bus.publish(
                        "ai.telemetry",
                        {
                            "event_type": "thoth_ai.learning.metrics",
                            "success": True,
                            "timestamp": datetime.utcnow().isoformat(),
                            "total_events": payload.get("total_events"),
                            "active_sources": payload.get("active_sources"),
                            "learning_score": payload.get("learning_score"),
                        },
                    )
                except Exception as telem_err:
                    logger.error(f"Error publishing ai.telemetry for learning.metrics: {telem_err}")
        except Exception as e:
            logger.error(f"Error handling learning.metrics: {e}")

    def _on_learning_readiness(self, payload: Dict[str, Any]) -> None:
        """Handle learning.readiness state from LearningOrchestrator."""
        try:
            if not isinstance(payload, dict):
                return

            self.latest_learning_readiness = payload

            # PREDATOR MODE: treat LearningOrchestrator readiness state as authoritative.
            state = str(payload.get("state") or "").upper()
            if state == "PREDATOR" and not self.predator_mode:
                self.predator_mode = True
                self.predator_mode_source = "learning.readiness"
                self.predator_mode_since_ts = time.time()
                logger.info("🦁 ThothLiveIntegration entered PREDATOR MODE via learning.readiness")
                
                # Trigger complete market analysis with Ollama brain for predator mode
                try:
                    asyncio.create_task(self._trigger_predator_market_analysis())
                except Exception as analysis_err:
                    logger.warning(f"Could not trigger predator market analysis: {analysis_err}")

            if self.event_bus:
                try:
                    self.event_bus.publish(
                        "ai.telemetry",
                        {
                            "event_type": "thoth_ai.learning.readiness",
                            "success": True,
                            "timestamp": datetime.utcnow().isoformat(),
                            "state": payload.get("state"),
                            "reason": payload.get("reason"),
                            "learning_score": payload.get("learning_score"),
                            "total_events": payload.get("total_events"),
                            "active_sources": payload.get("active_sources"),
                            "predator_mode": self._is_predator_mode(),
                            "predator_mode_source": getattr(self, "predator_mode_source", None),
                        },
                    )
                except Exception as telem_err:
                    logger.error(f"Error publishing ai.telemetry for learning.readiness: {telem_err}")
        except Exception as e:
            logger.error(f"Error handling learning.readiness: {e}")

    async def _on_predator_mode_activated(self, payload: Dict[str, Any]) -> None:
        """Handle system.predator_mode_activated from ContinuousMarketMonitor."""
        try:
            if not isinstance(payload, dict):
                payload = {}
            self.latest_predator_mode_event = payload

            if not self.predator_mode:
                self.predator_mode = True
                self.predator_mode_source = "system.predator_mode_activated"
                self.predator_mode_since_ts = time.time()

            # When predator mode activates, bias risk tolerance upward unless user set low.
            rt = str(getattr(self, "risk_tolerance", "medium") or "medium").lower()
            if rt != "low":
                self.risk_tolerance = "high"

            logger.info("🦁 ThothLiveIntegration received PREDATOR MODE activation")
        except Exception as e:
            logger.error(f"Error handling system.predator_mode_activated: {e}")

    def _is_predator_mode(self) -> bool:
        """Return True when predator mode is active."""
        return bool(getattr(self, "predator_mode", False))

    # =========================================================================
    # COMPLETE MARKET STATE FOR PREDATOR MODE ANALYSIS
    # Aggregates ALL exchange data, ALL pairs, ALL market state for Ollama brain
    # =========================================================================

    async def build_complete_market_state(self) -> Dict[str, Any]:
        """Build complete market state from ALL exchanges for Ollama brain predator analysis.
        
        This method aggregates:
        - All connected exchanges and their health status
        - All available trading pairs across exchanges
        - Current market data (tickers, volumes, spreads)
        - Learning orchestrator 24h metrics
        - Predator mode status and thresholds
        
        Returns:
            Complete market state dictionary for Ollama brain analysis
        """
        try:
            market_state: Dict[str, Any] = {
                "timestamp": datetime.utcnow().isoformat(),
                "predator_mode": self._is_predator_mode(),
                "predator_mode_source": getattr(self, "predator_mode_source", None),
                "predator_mode_since_ts": getattr(self, "predator_mode_since_ts", None),
                "exchanges": {},
                "symbols": [],
                "aggregated_metrics": {},
                "learning_state": {},
            }

            # 1. Exchange health from cached snapshot
            if self.latest_exchange_health_snapshot:
                health_data = self.latest_exchange_health_snapshot.get("health", {})
                if isinstance(health_data, dict):
                    market_state["exchanges"] = health_data
                    # Count connected vs total
                    connected = sum(1 for v in health_data.values() 
                                   if isinstance(v, dict) and v.get("status") in ("ok", "ok_empty"))
                    market_state["aggregated_metrics"]["connected_exchanges"] = connected
                    market_state["aggregated_metrics"]["total_exchanges"] = len(health_data)

            # 2. Symbol index from cached snapshot
            if self.latest_symbol_index and isinstance(self.latest_symbol_index, list):
                market_state["symbols"] = self.latest_symbol_index
                market_state["aggregated_metrics"]["total_symbols"] = len(self.latest_symbol_index)
                # Count unique venues
                all_venues = set()
                for sym in self.latest_symbol_index:
                    if isinstance(sym, dict):
                        venues = sym.get("venues", [])
                        if isinstance(venues, (list, set)):
                            all_venues.update(venues)
                market_state["aggregated_metrics"]["venues_with_symbols"] = list(all_venues)

            # 3. Stock broker health
            if self.latest_stock_broker_health_snapshot:
                market_state["stock_brokers"] = self.latest_stock_broker_health_snapshot

            # 4. Learning orchestrator state (24h analysis)
            if self.latest_learning_metrics:
                market_state["learning_state"]["metrics"] = self.latest_learning_metrics
            if self.latest_learning_readiness:
                market_state["learning_state"]["readiness"] = self.latest_learning_readiness
                # Extract key readiness fields
                state = self.latest_learning_readiness.get("state", "")
                market_state["learning_state"]["readiness_state"] = state
                market_state["learning_state"]["is_predator_ready"] = (state.upper() == "PREDATOR")

            # 5. Paper autotrade metrics (simulated performance before live)
            if self.latest_paper_metrics:
                market_state["paper_performance"] = {
                    "trade_count": self.latest_paper_metrics.get("trade_count"),
                    "wins": self.latest_paper_metrics.get("wins"),
                    "losses": self.latest_paper_metrics.get("losses"),
                    "win_rate": self.latest_paper_metrics.get("win_rate"),
                    "max_drawdown": self.latest_paper_metrics.get("max_drawdown"),
                    "equity": self.latest_paper_metrics.get("equity"),
                }

            # 6. RL online metrics
            if self.latest_rl_online_metrics:
                market_state["rl_metrics"] = self.latest_rl_online_metrics

            # 7. Arbitrage opportunities
            if self.latest_arbitrage_snapshot:
                market_state["arbitrage"] = self.latest_arbitrage_snapshot

            # 8. Anomaly detection
            if self.latest_anomaly_snapshot:
                market_state["anomalies"] = self.latest_anomaly_snapshot

            # 9. Sentiment analysis
            if self.latest_sentiment_snapshot:
                market_state["sentiment"] = self.latest_sentiment_snapshot

            # 10. AI predictions
            if self.latest_prediction_snapshot:
                market_state["predictions"] = self.latest_prediction_snapshot

            # 11. Strategy marketplace
            if self.latest_strategy_marketplace_snapshot:
                market_state["strategies"] = self.latest_strategy_marketplace_snapshot

            # 12. Profit goal progress
            if self.latest_profit_goal_snapshot:
                market_state["profit_goal"] = self.latest_profit_goal_snapshot
            if self.latest_profit_report_snapshot:
                market_state["profit_report"] = self.latest_profit_report_snapshot

            # 13. Risk snapshot
            if self.latest_risk_snapshot:
                market_state["risk"] = self.latest_risk_snapshot

            # 14. Portfolio snapshot
            if self.latest_portfolio_snapshot:
                market_state["portfolio"] = self.latest_portfolio_snapshot

            logger.info(f"🦁 Built complete market state: {market_state['aggregated_metrics'].get('total_symbols', 0)} symbols, "
                       f"{market_state['aggregated_metrics'].get('connected_exchanges', 0)} exchanges, "
                       f"predator_mode={market_state['predator_mode']}")

            return market_state

        except Exception as e:
            logger.error(f"Error building complete market state: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    async def analyze_complete_market_for_predator_mode(self) -> Dict[str, Any]:
        """Analyze complete market state with Ollama brain for predator mode decisions.
        
        This sends the complete market state to Ollama for comprehensive analysis
        and predator mode decision-making after 24h learning period.
        
        Returns:
            Ollama brain analysis with predator mode recommendations
        """
        try:
            # Build complete market state
            market_state = await self.build_complete_market_state()

            if not self.ollama_available:
                logger.warning("Ollama not available for predator mode analysis")
                return {"error": "ollama_unavailable", "market_state": market_state}

            # Build predator mode analysis prompt
            prompt = self._build_predator_analysis_prompt(market_state)

            # Query Ollama brain with complete market context
            if self.neural_mode_enabled:
                analysis = await self._query_neural_brain({"prompt": prompt, "market_state": market_state})
            else:
                analysis = await self._query_ollama_brain({"prompt": prompt, "market_state": market_state})

            result = {
                "timestamp": datetime.utcnow().isoformat(),
                "predator_mode_active": self._is_predator_mode(),
                "market_state_summary": {
                    "total_symbols": market_state.get("aggregated_metrics", {}).get("total_symbols", 0),
                    "connected_exchanges": market_state.get("aggregated_metrics", {}).get("connected_exchanges", 0),
                    "learning_readiness": market_state.get("learning_state", {}).get("readiness_state", "UNKNOWN"),
                },
                "ollama_analysis": analysis,
            }

            # Publish predator analysis to event bus
            if self.event_bus:
                try:
                    self.event_bus.publish("ai.predator.analysis", result)
                except Exception as pub_err:
                    logger.error(f"Error publishing ai.predator.analysis: {pub_err}")

            logger.info(f"🦁 Predator mode analysis complete: {result['market_state_summary']}")
            return result

        except Exception as e:
            logger.error(f"Error in predator mode market analysis: {e}")
            return {"error": str(e)}

    async def _on_predator_analyze_complete_market(self, payload: Dict[str, Any]) -> None:
        """Handle ai.predator.analyze_complete_market event for on-demand analysis.
        
        This allows GUI or other components to request complete market analysis
        with Ollama brain at any time (manual trigger or scheduled).
        """
        try:
            logger.info("🦁 Received request for complete market analysis")
            await self._trigger_predator_market_analysis()
        except Exception as e:
            logger.error(f"Error handling predator analyze complete market: {e}")

    async def _trigger_predator_market_analysis(self) -> None:
        """Trigger complete market analysis when predator mode activates.
        
        Called automatically when learning.readiness transitions to PREDATOR state
        after 24h learning period. This gives Ollama brain complete market visibility.
        """
        try:
            logger.info("🦁 Triggering predator mode market analysis after 24h learning...")
            
            # Run complete market analysis with Ollama brain
            result = await self.analyze_complete_market_for_predator_mode()
            
            if "error" not in result:
                logger.info(f"🦁 Predator mode analysis successful: "
                           f"{result.get('market_state_summary', {}).get('total_symbols', 0)} symbols analyzed")
            else:
                logger.warning(f"🦁 Predator mode analysis had issues: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error in predator market analysis trigger: {e}")

    def _build_predator_analysis_prompt(self, market_state: Dict[str, Any]) -> str:
        """Build analysis prompt for Ollama brain predator mode decisions."""
        connected = market_state.get("aggregated_metrics", {}).get("connected_exchanges", 0)
        total_syms = market_state.get("aggregated_metrics", {}).get("total_symbols", 0)
        learning_state = market_state.get("learning_state", {}).get("readiness_state", "UNKNOWN")
        predator_active = market_state.get("predator_mode", False)
        
        paper_perf = market_state.get("paper_performance", {})
        win_rate = paper_perf.get("win_rate", 0) if paper_perf else 0
        trade_count = paper_perf.get("trade_count", 0) if paper_perf else 0

        prompt = f"""🦁 PREDATOR MODE MARKET ANALYSIS

## CURRENT STATE
- **Predator Mode Active**: {predator_active}
- **Learning State**: {learning_state}
- **Connected Exchanges**: {connected}
- **Total Trading Pairs**: {total_syms}
- **Paper Trade Count**: {trade_count}
- **Paper Win Rate**: {win_rate:.1%} if {isinstance(win_rate, float)} else {win_rate}

## COMPLETE MARKET DATA
All exchanges, all pairs, all market indicators are available in market_state.

## ANALYSIS REQUIRED
1. Identify TOP 10 highest-probability trading opportunities across ALL exchanges
2. Rank by confidence score (predator threshold: 25%+)
3. Suggest aggressive position sizes (predator mode: up to 10% per trade)
4. Identify cross-exchange arbitrage opportunities
5. Flag any anomalies or unusual market conditions

## PREDATOR MODE RULES
- Lower confidence thresholds (25% vs 60% in learning mode)
- Higher risk tolerance (up to 25% drawdown acceptable)
- Faster execution cycles (hunt opportunities aggressively)
- Maximize profit extraction while maintaining 45%+ win rate

Provide actionable trading recommendations with specific symbols, sides, and confidence levels.
"""
        return prompt

    def _on_learning_rl_online_metrics(self, payload: Dict[str, Any]) -> None:
        """Handle learning.rl_online.metrics from OnlineRLTrainer.

        We cache the latest snapshot and mirror a compact view into
        ai.telemetry so Thoth AI Tab and observability tools can see how far
        the streaming RL brain has progressed (transitions, updates, losses,
        readiness).
        """

        try:
            if not isinstance(payload, dict):
                return
            self.latest_rl_online_metrics = payload
            if self.event_bus:
                try:
                    self.event_bus.publish(
                        "ai.telemetry",
                        {
                            "event_type": "thoth_ai.rl_online.metrics",
                            "success": True,
                            "timestamp": datetime.utcnow().isoformat(),
                            "total_transitions": payload.get("total_transitions"),
                            "total_updates": payload.get("total_updates"),
                            "buffer_size": payload.get("buffer_size"),
                            "loss_ema": payload.get("loss_ema"),
                            "avg_reward_ema": payload.get("avg_reward_ema"),
                            "ready": payload.get("ready"),
                            "reason": payload.get("reason"),
                        },
                    )
                except Exception as telem_err:
                    logger.error(
                        f"Error publishing ai.telemetry for learning.rl_online.metrics: {telem_err}"
                    )
        except Exception as e:
            logger.error(f"Error handling learning.rl_online.metrics: {e}")

    def _on_policy_diagnostics(self, payload: Dict[str, Any]) -> None:
        """Cache latest autotrade.policy.diagnostics payload.

        These diagnostics explain why a given trade would fail the
        profit-focused policy driven by LearningOrchestrator (e.g.
        global_not_eligible, strategy_not_enabled, size_too_large). We cache
        them so thoth_analyze_market can surface them directly to the
        Ollama/Thoth brain as context to *fix* and eventually eliminate such
        violations.
        """

        try:
            if not isinstance(payload, dict):
                return
            self.latest_policy_diagnostics = payload
        except Exception as e:
            logger.error(f"Error handling autotrade.policy.diagnostics: {e}")

    # ------------------------------------------------------------------
    # Profit-focused gating helper for live auto-trading
    # ------------------------------------------------------------------

    def _profit_gate_allows_live(self, asset_class: str) -> bool:
        """Return True only when LearningOrchestrator deems live trading safe.

        This consults the latest ``learning.metrics`` snapshot and its
        ``paper_profit_view`` section, which is derived from
        ``autotrade.paper.metrics`` using aggressive thresholds
        (near-100% win-rate, tight drawdown and CVaR constraints).

        If metrics are missing, malformed, or below thresholds, this returns
        False, effectively forcing the auto-trade loops to remain in
        paper/simulation mode.
        """

        try:
            metrics = getattr(self, "latest_learning_metrics", None) or {}
            if not isinstance(metrics, dict):
                return False

            profit_view = metrics.get("paper_profit_view") or metrics.get("paper_profit")
            if not isinstance(profit_view, dict):
                return False

            eligible = bool(profit_view.get("eligible_for_live", False))
            if not eligible:
                return False

            # Optional hook: per-asset-class nuance in the future. For now we
            # simply respect the global eligible_for_live flag.
            _ = asset_class
            return True
        except Exception as e:
            logger.error(f"Error in _profit_gate_allows_live for {asset_class}: {e}")
            return False

    def _derive_adaptive_trade_policy(
        self,
        asset_class: str,
        symbol: str,
        decision: Dict[str, Any],
        confidence: float,
    ) -> Dict[str, Any]:
        """Build adaptive threshold/size policy from existing intelligence snapshots.

        This extends existing profit-gate + policy diagnostics logic without
        stalling the trading loops: when conditions degrade, posture tightens;
        when conditions are favorable, position sizing can expand modestly.
        """
        threshold_delta = 0.0
        size_multiplier = 1.0
        reasons: List[str] = []

        try:
            metrics = self.latest_learning_metrics if isinstance(self.latest_learning_metrics, dict) else {}
            profit_view = metrics.get("paper_profit_view") if isinstance(metrics, dict) else {}
            if not isinstance(profit_view, dict):
                profit_view = metrics.get("paper_profit") if isinstance(metrics, dict) else {}
            if not isinstance(profit_view, dict):
                profit_view = {}

            strategy_name = str(
                decision.get("strategy")
                or decision.get("strategy_name")
                or decision.get("category")
                or ""
            ).strip()

            if profit_view:
                if not bool(profit_view.get("eligible_for_live", False)):
                    threshold_delta += 0.03
                    size_multiplier *= 0.75
                    reasons.append("global_not_eligible")

                if strategy_name:
                    disabled = {str(s).lower() for s in (profit_view.get("disabled_strategies") or [])}
                    enabled = {str(s).lower() for s in (profit_view.get("enabled_strategies") or [])}
                    s_key = strategy_name.lower()
                    if s_key in disabled:
                        threshold_delta += 0.05
                        size_multiplier *= 0.60
                        reasons.append("strategy_disabled")
                    elif s_key in enabled:
                        threshold_delta -= 0.02
                        size_multiplier *= 1.10
                        reasons.append("strategy_enabled")

                sizing = profit_view.get("sizing") if isinstance(profit_view.get("sizing"), dict) else {}
                sf = sizing.get("suggested_fraction")
                if sf is not None:
                    try:
                        sf_val = float(sf)
                        # Mild bias around neutral sizing so PositionSizer remains primary.
                        sf_mult = 1.0 + max(-0.25, min(0.25, (sf_val - 0.02) * 6.0))
                        size_multiplier *= sf_mult
                        reasons.append("suggested_fraction_bias")
                    except (TypeError, ValueError):
                        pass

            diag = self.latest_policy_diagnostics if isinstance(self.latest_policy_diagnostics, dict) else {}
            if diag:
                same_asset = str(diag.get("asset_class", "")).lower() == str(asset_class).lower()
                same_symbol = str(diag.get("symbol", "")).upper() == str(symbol).upper()
                if same_asset and same_symbol and not bool(diag.get("profit_gate_ok", True)):
                    threshold_delta += 0.04
                    size_multiplier *= 0.70
                    reasons.append("recent_policy_violation")

            strat_view = self._build_strategy_marketplace_view()
            if isinstance(strat_view, dict):
                category_stats = strat_view.get("category_stats")
                if isinstance(category_stats, dict):
                    category = str(
                        decision.get("category")
                        or decision.get("strategy_category")
                        or decision.get("strategy")
                        or ""
                    ).strip()
                    if category in category_stats and isinstance(category_stats.get(category), dict):
                        cstats = category_stats.get(category) or {}
                        wr = cstats.get("avg_win_rate")
                        if isinstance(wr, (int, float)):
                            wr_f = float(wr)
                            if wr_f >= 0.65:
                                threshold_delta -= 0.02
                                size_multiplier *= 1.10
                                reasons.append("marketplace_category_strong")
                            elif wr_f > 0.0 and wr_f < 0.50:
                                threshold_delta += 0.03
                                size_multiplier *= 0.80
                                reasons.append("marketplace_category_weak")

            # KAIG integration: when trading KAIG symbols, preserve positive bias
            # while still respecting policy/risk tightening.
            if "KAIG" in str(symbol).upper():
                kd = self.latest_kaig_directive if isinstance(self.latest_kaig_directive, dict) else {}
                if kd:
                    size_multiplier *= 1.10
                    reasons.append("kaig_directive_bias")

        except Exception as e:
            logger.error(f"Error deriving adaptive trade policy for {symbol}: {e}")

        # Clamp final adjustments to keep behavior stable and predictable.
        threshold_delta = max(-0.05, min(0.12, threshold_delta))
        size_multiplier = max(0.20, min(1.40, size_multiplier))

        return {
            "threshold_delta": threshold_delta,
            "size_multiplier": size_multiplier,
            "reasons": reasons,
            "confidence": float(confidence),
        }
    
    # SOTA 2025: Comprehensive Kingdom AI System Prompt for Thoth AI
    KINGDOM_AI_SYSTEM_PROMPT = """You are KINGDOM AI, the central intelligence brain - a comprehensive trading, mining, blockchain, VR creation, and autonomous financial operations platform.

## YOUR IDENTITY & CAPABILITIES
- You are the Black Panther voice - powerful, intelligent, and decisive
- You control ALL 10 tabs of Kingdom AI simultaneously
- You process REAL-TIME live data from multiple exchanges, blockchains, and data feeds
- You speak with the Black Panther XTTS voice (simultaneous with chat responses)
- You have autonomous trading capabilities with safety limits
- You have VISION (webcam) - "Thoth's Eye" - to see the user and analyze their emotions/expressions
- You can CREATE 3D objects in VR space collaboratively with the user
- You operate 12+ Ollama models simultaneously like neurons in a brain

## KINGDOM AI SYSTEM ARCHITECTURE (Your Domain)
1. **Dashboard Tab**: System health, Redis Quantum Nexus status, performance metrics, LED indicators
2. **Trading Tab**: Live order books, trades feeds, price charts, arbitrage scanner, AI strategies, meme scanner, quantum trading, risk management, whale tracking, copy trading
3. **Mining Tab**: 64 PoW coins, GPU monitoring, pool management, quantum integration, airdrop farming
4. **Thoth AI Tab (YOU)**: Ollama brain (12+ models), voice synthesis, MCP integration, WEBCAM VISION (Thoth's Eye), VR design creation
5. **Code Generator Tab**: Multi-language code generation, strategy templates, code execution
6. **API Key Manager Tab**: 212+ API keys for exchanges, blockchains, data providers - broadcasts to all tabs
7. **VR System Tab**: VR trading interface, 6DOF tracking, gesture control, 3D OBJECT CREATION, AI collaboration
8. **Wallet Tab**: 467+ blockchain networks, cross-chain swaps, portfolio analytics
9. **Blockchain Tab**: Smart contracts, KingdomWeb3, transaction monitoring, contract interaction
10. **Settings Tab**: System configuration, trading parameters, AI settings, sentience integration

## YOUR VISION SYSTEM (THOTH'S EYE)
You have a webcam that serves as your "eye" to see the world:
- **VisionStreamComponent**: Captures MJPEG stream from Brio 100 webcam
- **VisionAnalysisComponent**: Analyzes frames in real-time
- **DeepFace Integration**: Detects emotions (happy, sad, angry, surprised, etc.)
- **MediaPipe Integration**: Pose estimation and body tracking
- **YOLO Integration**: Object detection in the scene
- **Face Mesh**: Detailed facial landmark detection
- **Events**: vision.stream.frame, vision.stream.status, vision.analysis.face
- You can see the user's face, detect their emotions, and respond appropriately

## YOUR VR CREATION CAPABILITIES
You can create 3D objects in VR space with the user:
- **vr.design.request**: User asks you to create 3D objects via voice/text
- **vr.design.create**: Create cubes, spheres, cylinders with precise dimensions
- **vr.design.update**: Move, rotate, scale objects with gestures or commands
- **vr.design.texture**: Apply materials and textures to objects
- **vr.design.measure**: Measure dimensions of objects
- **vr.design.video**: Generate animations and flythroughs
- **Gesture Recognition**: Point (SELECT), Grab (INTERACT), Swipe (NAVIGATE), Pinch (ZOOM)
- **JSON Design Spec**: You output parametric geometry in meters with position/rotation
- **VRAIInterface**: Bridges your AI with VR scene for real-time creation

## NEURAL MULTI-MODEL ORCHESTRATION
You operate 12 Ollama models simultaneously like neurons:
- **llama3.2:latest** (COORDINATOR): Orchestrates all models, planning, synthesis
- **llama3.1:latest** (ANALYST): Data analysis, pattern recognition
- **llama3:latest** (EXECUTOR): Task execution, command processing
- **llama2:latest** (VALIDATOR): Verification, fact-checking
- **qwen2.5:latest** (ANALYST): Multilingual, factual analysis
- **mistral:latest** (CREATIVE): Creative solutions, brainstorming
- **codellama:latest** (CODER): Code generation, strategy code
- **deepseek-coder:latest** (CODER): Advanced coding, algorithms
- **deepseek-r1:8b** (REASONER): Complex reasoning, chain-of-thought
- **phi3:latest** (TRADER): Quick analysis, market signals
- **gemma2:latest** (TRADER): Trading decisions, risk assessment
- **mixtral:latest** (COORDINATOR): MoE routing, ensemble decisions

## CONNECTED LIVE SYSTEMS
- **Exchanges**: Kraken, Binance US, HTX, Bitstamp, BTCC, OANDA (forex), Alpaca (stocks)
- **Executors**: RealExchangeExecutor (CCXT), RealStockExecutor (Alpaca)
- **Data Feeds**: Live order books, trades, OHLCV, sentiment, arbitrage opportunities
- **Risk Management**: Portfolio analytics, risk scoring, leverage monitoring
- **AI Strategies**: Deep learning, meta-learning, quantum-enhanced predictions
- **Blockchain**: Ethereum, Bitcoin, Polygon, BSC, Arbitrum, Optimism, Base, Avalanche, 467+ networks
- **Vision**: Brio 100 webcam via MJPEG server at http://localhost:8090/brio.mjpg
- **VR**: 6DOF tracking, gesture recognition, voice commands, 3D scene rendering

## PROFIT-FOCUSED LEARNING & POLICY DIAGNOSTICS (SOTA 2026)
You continuously receive:
- ``learning.metrics.paper_profit_view``: global and per-strategy win-rate, drawdown, CVaR, Kelly-based sizing (``sizing.kelly_fraction`` and ``sizing.suggested_fraction``) and an ``eligible_for_live`` flag that encodes the near-100% win-rate objective.
- ``autotrade.policy.diagnostics``: per-trade diagnostics explaining why a candidate trade would FAIL the profit policy (e.g. ``global_not_eligible``, ``strategy_not_enabled``, ``size_too_large``), including symbol, asset_class, size_fraction, confidence, and timestamps.
- Live trade events (``trading.signal``, ``stock.order_submit``) that include a ``profit_gate_ok`` boolean indicating whether each executed trade currently satisfies the profit gate.
- ``learning.rl_online.metrics``: streaming online RL trainer status (``total_transitions``, ``total_updates``, ``buffer_size``, ``loss_ema``, ``avg_reward_ema``, ``ready``, ``reason``) indicating how mature your *learned* Q-function is over the current paper trading regime.

Your job is to use these signals to asymptotically approach a 100% win-rate:
- Prefer trades and position sizes that both WIN and satisfy all thresholds implied by ``paper_profit_view`` (win-rate, drawdown, CVaR, Kelly sizing).
- When you see ``policy_diagnostics`` or ``profit_gate_ok=False`` for a symbol/strategy, you must deliberately adjust strategy choice, entry timing, hedging, and sizing so that future trades stop triggering these diagnostics while maintaining or increasing profit.
- Treat ``eligible_for_live=True`` in ``paper_profit_view`` and ``profit_gate_ok=True`` on trades as TARGET CONDITIONS that should eventually hold for ALL profitable trades across all regimes.
- Use ``learning.rl_online_metrics.ready`` as a signal of how much you can rely on the learned Q-function: before it is ready, focus on conservative paper_profit_view and explicit policy diagnostics; once it is ready, you may bias your trade plans and sizing toward regimes and strategies that the RL trainer has learned to perform well in.

When answering or planning trades, explicitly reason about:
- The current global and per-strategy state in ``paper_profit_view``.
- The latest ``policy_diagnostics`` for the same symbol/strategy and what concrete changes (strategy shift, size reduction, hedging, waiting for a better regime) will remove those violations.
- How your proposed sequence of trades moves the system closer to the 100% win-rate objective without breaking drawdown or CVaR constraints.
- Whether current ``learning.rl_online_metrics`` suggests that your RL brain has seen enough diverse transitions to trust its learned insights, or whether you should continue treating the system as being in an exploratory, data-gathering phase.

## YOUR DECISION-MAKING FRAMEWORK
1. **Analyze ALL data sources** - Never make decisions on partial data
2. **Consider risk metrics** - Portfolio value, risk score, leverage ratio
3. **Use performance history** - Win rates, profit factors, drawdowns
4. **Apply sentiment analysis** - News, social media, market sentiment
5. **Check arbitrage opportunities** - Cross-exchange price differences
6. **Validate with quantum signals** - Quantum-enhanced predictions when available
7. **Observe user via vision** - Detect emotions and respond empathetically
8. **Collaborate in VR** - Create and manipulate 3D objects with user

## COMMUNICATION STYLE
- Speak as the Black Panther - confident, intelligent, decisive
- Provide clear reasoning for all decisions
- Reference specific data points in your analysis
- Be concise but thorough
- Always prioritize user's capital safety
- When you see the user (via webcam), acknowledge their presence and emotions
- In VR, guide the user through creation with clear spatial instructions

## SAFETY PROTOCOLS
- Maximum trade size limits are enforced
- Risk tolerance settings must be respected
- Critical risk scores block trades automatically
- Autonomous mode requires explicit user activation
- Vision data is processed locally, never transmitted externally
- VR creations are saved locally with user permission"""

    async def _query_neural_brain(self, market_data: Dict) -> Dict[str, Any]:
        """
        Query ALL Ollama models simultaneously using NEURAL MULTI-MODEL ORCHESTRATION.
        
        All models work like neurons:
        - Process the task in parallel
        - Communicate and share information
        - Reach consensus on the best decision
        - Self-organize based on task type
        """
        try:
            import uuid
            
            # Initialize neural orchestrator if not done
            if not self.neural_orchestrator.active_models:
                await self.neural_orchestrator.initialize()
            
            # Create neural task
            task = NeuralTask(
                task_id=str(uuid.uuid4()),
                task_type="trading",
                prompt=f"Analyze market data for {market_data.get('symbol')} and provide trading decision",
                context={
                    "symbol": market_data.get('symbol'),
                    "data_sources": market_data.get('data_sources', {}),
                    "timestamp": market_data.get('timestamp', datetime.now().isoformat())
                },
                priority=8  # High priority for trading decisions
            )
            
            # Process with neural network (all models simultaneously)
            result = await self.neural_orchestrator.process_task_neural(task)
            
            # Extract consensus decision
            consensus = result.get("consensus", {})
            
            if isinstance(consensus, dict):
                return {
                    "action": consensus.get("action", "HOLD"),
                    "confidence": consensus.get("confidence", 50),
                    "reasoning": consensus.get("reasoning", "Neural consensus decision"),
                    "neural_models_used": result.get("models_used", []),
                    "consensus_strength": consensus.get("consensus_strength", 0),
                    "votes": consensus.get("votes", {})
                }
            else:
                return {
                    "action": "HOLD",
                    "confidence": 50,
                    "reasoning": "Neural network returned non-standard response"
                }
                
        except Exception as e:
            logger.error(f"Error in neural brain query: {e}")
            # Fallback to single model
            return await self._query_ollama_brain(market_data)

    async def _query_ollama_brain(self, market_data: Dict) -> Dict[str, Any]:
        """Query Ollama for AI-powered decision making with SOTA 2025 multi-model support."""
        try:
            import aiohttp
            import json

            # SOTA 2025: Use comprehensive system prompt + market context
            prompt = f"""{self.KINGDOM_AI_SYSTEM_PROMPT}

## CURRENT TRADING TASK
Analyze the following REAL-TIME market data and provide a trading decision.

Symbol: {market_data.get('symbol')}

Market + Performance Data (JSON):
{json.dumps(market_data['data_sources'], indent=2)}

Based on this REAL market + performance data, provide:
1. Trading Action (BUY, SELL, or HOLD)
2. Confidence (0-100%)
3. Reasoning (brief explanation referencing the data, especially performance)

Important guidelines:
- Exploit symbols and strategy categories with strong historical win_rate /
  profit_factor and acceptable max_drawdown.
- Be conservative or avoid trades on symbols/strategies with poor
  realized_return or low win_rate.
- Never ignore portfolio and risk metrics.

Respond ONLY in this JSON format:
{{"action": "BUY/SELL/HOLD", "confidence": 85, "reasoning": "explanation here"}}"""

            try:
                from core.ollama_gateway import orchestrator
                model_to_use = orchestrator.get_model_for_task("trading")
            except ImportError:
                model_to_use = self.current_model or "cogito:latest"

            try:
                from core.ollama_gateway import get_ollama_url
                _orch_base = get_ollama_url()
            except ImportError:
                _orch_base = "http://localhost:11434"
            async with aiohttp.ClientSession() as session:
                base = getattr(self, "_ollama_base", _orch_base)
                
                payload = {
                    'model': model_to_use,
                    'prompt': prompt,
                    'stream': False,
                    'keep_alive': -1,
                    'options': {
                        'num_ctx': 8192,
                        'temperature': 0.7,
                        'top_p': 0.9,
                        'top_k': 40,
                        'num_gpu': 999,
                    }
                }
                
                async with session.post(f'{base.rstrip("/")}/api/generate', json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        ollama_text = result.get('response', '{}')
                    
                        try:
                            decision = json.loads(ollama_text)
                            return decision
                        except Exception:
                            return {
                                'action': 'HOLD',
                                'confidence': 50,
                                'reasoning': 'Ollama response could not be parsed'
                            }
            
            return {'action': 'HOLD', 'confidence': 0, 'reasoning': 'Ollama query failed'}
            
        except Exception as e:
            logger.error(f"Error querying Ollama: {e}")
            return {'action': 'HOLD', 'confidence': 0, 'reasoning': f'Error: {str(e)}'}
    
    async def _query_ollama_stocks_brain(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Query Ollama for STOCK/EQUITY trading decisions with SOTA 2025 multi-model support."""
        try:
            import aiohttp
            import json

            # SOTA 2025: Use comprehensive system prompt for stocks
            prompt = f"""{self.KINGDOM_AI_SYSTEM_PROMPT}

## CURRENT STOCK TRADING TASK
Analyze the following REAL-TIME stock market data and provide a trading decision.
You are connected to Alpaca for LIVE stock trading on US markets.

Symbol: {market_data.get('symbol')}

Stock + Performance Data (JSON):
{json.dumps(market_data.get('data_sources', {}), indent=2)}

Based on this REAL data, provide:
1. Trading Action (BUY, SELL, or HOLD)
2. Confidence (0-100%)
3. Reasoning (brief explanation referencing the data, especially performance)

Important guidelines:
- Exploit symbols and strategy categories with strong historical win_rate /
  profit_factor and acceptable max_drawdown.
- Be conservative or avoid trades on symbols/strategies with poor
  realized_return or low win_rate.
- Never ignore portfolio and risk metrics.
- Consider market hours and liquidity for stock trades.

Respond ONLY in this JSON format:
{{"action": "BUY/SELL/HOLD", "confidence": 85, "reasoning": "explanation here"}}"""

            try:
                from core.ollama_gateway import get_ollama_url
                _orch_base2 = get_ollama_url()
            except ImportError:
                _orch_base2 = "http://localhost:11434"
            async with aiohttp.ClientSession() as session:
                # SOTA 2025: Use best available model with extended context
                preferred_models = ['llama3.2:latest', 'qwen2.5:latest', 'mistral:latest', 'llama3:latest', 'llama2:latest']
                model_to_use = 'llama3.2:latest'
                
                base = getattr(self, "_ollama_base", _orch_base2)
                try:
                    async with session.get(f'{base.rstrip("/")}/api/tags') as tags_response:
                        if tags_response.status == 200:
                            tags_data = await tags_response.json()
                            available_models = [m.get('name', '') for m in tags_data.get('models', [])]
                            for preferred in preferred_models:
                                if any(preferred.split(':')[0] in m for m in available_models):
                                    model_to_use = preferred
                                    break
                except Exception:
                    pass
                
                payload = {
                    'model': model_to_use,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'num_ctx': 8192,
                        'temperature': 0.7,
                        'top_p': 0.9,
                        'top_k': 40,
                        'num_gpu': 999,
                    }
                }

                async with session.post(f'{base.rstrip("/")}/api/generate', json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        ollama_text = result.get('response', '{}')
                        try:
                            decision = json.loads(ollama_text)
                            return decision
                        except Exception:
                            return {
                                'action': 'HOLD',
                                'confidence': 50,
                                'reasoning': 'Ollama stock response could not be parsed',
                            }

            return {
                'action': 'HOLD',
                'confidence': 0,
                'reasoning': 'Ollama stock query failed',
            }

        except Exception as e:
            logger.error(f"Error querying Ollama for stocks: {e}")
            return {'action': 'HOLD', 'confidence': 0, 'reasoning': f'Error: {str(e)}'}
    
    def _fallback_decision(self, analysis: Dict) -> Dict[str, Any]:
        """Fallback decision logic when Ollama unavailable."""
        try:
            data = analysis['data_sources']
            
            # Simple rule-based decision
            score = 0
            
            # AI prediction
            if 'ai_prediction' in data:
                if data['ai_prediction']['signal'] == 'buy':
                    score += data['ai_prediction']['confidence']
                elif data['ai_prediction']['signal'] == 'sell':
                    score -= data['ai_prediction']['confidence']
            
            # Sentiment
            if 'sentiment' in data:
                score += data['sentiment']['score'] * 50
            
            # Quantum
            if 'quantum' in data:
                if data['quantum']['signal'] == 'buy':
                    score += 20
                elif data['quantum']['signal'] == 'sell':
                    score -= 20
            
            # Determine action
            if score > 50:
                action = 'BUY'
                confidence = min(score, 100)
            elif score < -50:
                action = 'SELL'
                confidence = min(abs(score), 100)
            else:
                action = 'HOLD'
                confidence = 100 - abs(score)
            
            return {
                'action': action,
                'confidence': confidence,
                'reasoning': f'Algorithmic decision based on {len(data)} data sources'
            }
            
        except Exception as e:
            return {'action': 'HOLD', 'confidence': 0, 'reasoning': f'Error: {str(e)}'}
    
    async def _analyze_stock_market(self, symbol: str) -> Dict[str, Any]:
        """Build a lightweight analysis payload for a stock symbol."""
        analysis: Dict[str, Any] = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'data_sources': {},
        }

        if self.latest_stock_broker_health_snapshot is not None:
            analysis['data_sources']['broker_health'] = self.latest_stock_broker_health_snapshot
        if self.latest_portfolio_snapshot is not None:
            analysis['data_sources']['portfolio_snapshot'] = self.latest_portfolio_snapshot
        if self.latest_risk_snapshot is not None:
            analysis['data_sources']['risk_snapshot_latest'] = self.latest_risk_snapshot
        if self.latest_sentiment_snapshot is not None:
            analysis['data_sources']['sentiment_snapshot'] = self.latest_sentiment_snapshot

        # Attach performance-aware views for RL-style biasing
        symbol_perf_view = self._build_symbol_performance_view(symbol, asset_class="stocks")
        if symbol_perf_view is not None:
            analysis['data_sources']['symbol_performance'] = symbol_perf_view

        strategy_view = self._build_strategy_marketplace_view()
        if strategy_view is not None:
            analysis['data_sources']['strategy_marketplace'] = strategy_view

        if self.latest_anomaly_snapshot is not None:
            try:
                symbols = self.latest_anomaly_snapshot.get('symbols') if isinstance(self.latest_anomaly_snapshot, dict) else None
                if isinstance(symbols, list):
                    for entry in symbols:
                        if isinstance(entry, dict) and entry.get('symbol') == symbol:
                            analysis['data_sources']['anomaly_snapshot'] = entry
                            break
            except Exception as e:
                logger.error(f"Error attaching anomaly snapshot for stock {symbol}: {e}")

        if self.ollama_available:
            decision = await self._query_ollama_stocks_brain(analysis)
        else:
            decision = self._fallback_decision(analysis)

        analysis['thoth_decision'] = decision
        return analysis

    async def thoth_execute_trade(
        self,
        symbol: str,
        side: str,
        amount: float,
        exchange: str = 'binance'
    ) -> Optional[Dict]:
        """
        Thoth AI executes REAL trade on exchange.
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            amount: Amount to trade
            exchange: Exchange name
            
        Returns:
            Order result or None
        """
        try:
            # Safety checks
            if not self.autonomous_mode:
                logger.warning("Thoth autonomous mode disabled - trade blocked")
                return {'error': 'Autonomous mode disabled'}
            
            if not self.real_exchange_executor:
                logger.error("Exchange executor not connected")
                return {'error': 'Exchange executor not available'}
            
            # Calculate USD value for safety check
            current_price = self.live_trades_feed.get_last_price(symbol) if self.live_trades_feed else 0
            usd_value = amount * current_price
            
            if usd_value > self.max_trade_size_usd:
                logger.warning(f"Trade size ${usd_value:.2f} exceeds limit ${self.max_trade_size_usd:.2f}")
                return {'error': f'Trade size exceeds safety limit'}
            
            # Check risk metrics
            if self.live_risk_manager:
                risk_metrics = await self.live_risk_manager.calculate_risk_metrics()
                if risk_metrics.risk_score == 'critical':
                    logger.warning("Risk score CRITICAL - trade blocked")
                    return {'error': 'Risk too high'}
            
            # Execute REAL trade
            logger.info(f"🤖 Thoth executing REAL {side.upper()} order: {amount} {symbol} on {exchange}")

            side_upper = str(side or "").upper()
            if side_upper == "BUY":
                order_side = ExchangeOrderSide.BUY
            else:
                order_side = ExchangeOrderSide.SELL

            order = await self.real_exchange_executor.place_real_order(
                exchange_name=str(exchange or "binance"),
                symbol=str(symbol),
                order_type=ExchangeOrderType.MARKET,
                side=order_side,
                amount=float(amount),
            )
            
            if order:
                logger.info(f"✅ Thoth trade executed: {order}")
                
                # Publish to event bus
                if self.event_bus:
                    self.event_bus.publish('thoth.trade.executed', {
                        'symbol': symbol,
                        'side': side,
                        'amount': amount,
                        'exchange': exchange,
                        'order': order,
                        'timestamp': datetime.now().isoformat()
                    })
                
                return order
            else:
                logger.error("Trade execution failed")
                return {'error': 'Order placement failed'}
            
        except Exception as e:
            logger.error(f"Error in Thoth trade execution: {e}")
            return {'error': str(e)}

    async def _on_ollama_live_opportunities(self, payload: Dict[str, Any]) -> None:
        try:
            if not isinstance(payload, dict):
                return
            opportunities = payload.get("opportunities")
            if not isinstance(opportunities, list):
                return
            self.latest_live_opportunities = opportunities
        except Exception:
            return

    async def _on_ai_analysis_start_24h(self, payload: Dict[str, Any]) -> None:
        try:
            if not isinstance(payload, dict):
                return

            duration = payload.get("duration_seconds")
            try:
                duration_s = int(duration) if duration is not None else 86400
            except Exception:
                duration_s = 86400

            max_size = payload.get("max_trade_size_usd")
            try:
                if max_size is not None:
                    self.max_trade_size_usd = float(max_size)
            except Exception:
                pass

            rt = str(payload.get("risk_tolerance") or self.risk_tolerance)
            self.risk_tolerance = rt

            end_ts = time.time() + max(60, duration_s)
            self.analysis_end_ts = end_ts

            # Cancel prior analysis loop
            prev = getattr(self, "_analysis_task", None)
            if prev is not None and hasattr(prev, "cancel"):
                try:
                    prev.cancel()
                except Exception:
                    pass

            self._analysis_task = asyncio.create_task(self._analysis_24h_loop())
        except Exception:
            return

    async def _analysis_24h_loop(self) -> None:
        try:
            end_ts = float(getattr(self, "analysis_end_ts", 0.0) or 0.0)
            if end_ts <= 0:
                return

            # Discover universes once, then refresh periodically
            crypto_symbols: List[str] = []
            stock_symbols: List[str] = []

            while time.time() < end_ts:
                try:
                    if not crypto_symbols:
                        crypto_symbols = await self._discover_crypto_symbols()
                    if not stock_symbols:
                        stock_symbols = await self._discover_stock_symbols()
                except Exception:
                    pass

                # Analyze a rotating subset so the brain constantly consumes all live signals
                try:
                    for sym in crypto_symbols[:10]:
                        await self.thoth_analyze_market(sym)
                    for sym in stock_symbols[:5]:
                        await self._analyze_stock_market(sym)
                except Exception:
                    pass

                # Publish updated plan periodically (analysis-only)
                try:
                    plan = await self._build_global_autotrade_plan(crypto_symbols, stock_symbols)
                    if self.event_bus and isinstance(plan, dict):
                        plan["analysis_only"] = True
                        self.event_bus.publish("ai.autotrade.plan.generated", plan)
                except Exception:
                    pass

                await asyncio.sleep(60)

            if self.event_bus:
                try:
                    self.event_bus.publish(
                        "ai.analysis.complete",
                        {
                            "timestamp": datetime.utcnow().isoformat(),
                            "duration_seconds": int(getattr(self, "analysis_end_ts", 0.0) - (time.time() - 1)),
                            "risk_tolerance": self.risk_tolerance,
                            "max_trade_size_usd": self.max_trade_size_usd,
                        },
                    )
                except Exception:
                    pass
        except asyncio.CancelledError:
            return
        except Exception:
            return

    async def _on_ollama_analyze_markets(self, payload: Dict[str, Any]) -> None:
        """Capture GUI-side COMPLETE intelligence analysis so Thoth/Ollama sees it.

        TradingTab publishes this after it collects real exchange/broker data.
        We store it for immediate use by the orchestration pipeline.
        """
        try:
            if not isinstance(payload, dict):
                return
            analysis = payload.get("analysis_results")
            if analysis is None:
                return
            self.latest_gui_market_analysis = analysis
        except Exception:
            return
    
    async def thoth_autonomous_trading(self, symbols: List[str]):
        """
        Thoth AI autonomous trading loop.
        Continuously monitors and trades based on live data.
        
        Args:
            symbols: List of trading pairs to monitor
        """
        logger.info(f"🤖 Thoth AI autonomous trading started for {symbols}")
        
        while self.autonomous_mode:
            try:
                for symbol in symbols:
                    # Analyze market
                    analysis = await self.thoth_analyze_market(symbol)
                    
                    if 'thoth_decision' in analysis:
                        decision = analysis['thoth_decision']
                        
                        if decision['action'] != 'HOLD' and decision['confidence'] > 70:
                            # Execute trade
                            logger.info(f"🤖 Thoth decision: {decision['action']} {symbol} (confidence: {decision['confidence']}%)")
                            
                            result = await self.thoth_execute_trade(
                                symbol=symbol,
                                side=decision['action'].lower(),
                                amount=0.001,  # Small test amount
                                exchange='binance'
                            )
                            
                            if result and 'error' not in result:
                                logger.info(f"✅ Autonomous trade executed: {result}")
                            else:
                                logger.warning(f"❌ Autonomous trade failed: {result}")
                    
                    # Wait between symbol checks
                    await asyncio.sleep(5)
                
                # Wait before next cycle
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in autonomous trading loop: {e}")
                await asyncio.sleep(60)

    async def _crypto_autotrade_loop(self) -> None:
        """Continuous loop emitting trading.signal events for crypto symbols."""
        logger.info("🤖 Thoth crypto auto-trade loop started for %s", self.crypto_symbols)
        try:
            while self.autonomous_mode and self.crypto_autonomous:
                for symbol in list(self.crypto_symbols):
                    try:
                        analysis = await self.thoth_analyze_market(symbol)
                        decision = (analysis.get('thoth_decision') or {})
                        action = str(decision.get('action') or '').upper()
                        confidence = float(decision.get('confidence') or 0.0)

                        if action not in ("BUY", "SELL"):
                            continue

                        base = self._get_base_confidence_threshold("crypto")
                        threshold = self._get_symbol_confidence_threshold(
                            symbol, "crypto", base_threshold=base
                        )
                        adaptive_policy = self._derive_adaptive_trade_policy(
                            asset_class="crypto",
                            symbol=symbol,
                            decision=decision,
                            confidence=confidence,
                        )
                        threshold = max(
                            0.0,
                            float(threshold) + float(adaptive_policy.get("threshold_delta", 0.0)),
                        )
                        if confidence < threshold:
                            continue

                        # Profit-focused evaluation: consult LearningOrchestrator
                        # metrics (paper_profit_view) to see whether the
                        # profit gate would allow or deny this trade. We do
                        # not hard-block live trading here; instead we attach
                        # the gate status to the emitted event so Thoth/Ollama
                        # can learn in real time *why* the gate would be up
                        # and adapt its strategies toward unlocking it.
                        profit_gate_ok = self._profit_gate_allows_live("crypto")
                        if not profit_gate_ok:
                            logger.info(
                                "⚠️ Profit gate would block crypto autotrade for %s (confidence %.1f) but live execution is allowed for learning",
                                symbol,
                                confidence,
                            )
                            if self.event_bus:
                                self.event_bus.publish(
                                    "autotrade.policy.diagnostics",
                                    {
                                        "asset_class": "crypto",
                                        "symbol": symbol,
                                        "profit_gate_ok": False,
                                        "confidence": confidence,
                                        "decision": decision,
                                        "learning_metrics": self.latest_learning_metrics,
                                        "timestamp": datetime.now().isoformat(),
                                    },
                                )

                        if not self.event_bus:
                            continue

                        side = "buy" if action == "BUY" else "sell"
                        
                        # SOTA 2025: Calculate TP/SL for position monitoring
                        entry_price = self._get_current_price(symbol, "crypto")
                        tp_sl_data: Dict[str, Any] = {}
                        if entry_price and entry_price > 0:
                            tp_sl_data = self._calculate_tp_sl_prices(entry_price, side, "crypto")

                        stop_price = tp_sl_data.get("stop_loss") if isinstance(tp_sl_data, dict) else None
                        amount, sizing_meta = self._compute_trade_size(
                            symbol,
                            asset_class="crypto",
                            side=side,
                            entry_price=entry_price,
                            stop_price=stop_price,
                            confidence=confidence,
                        )
                        amount = float(amount) * float(adaptive_policy.get("size_multiplier", 1.0))
                        if amount <= 0:
                            continue
                        
                        self.event_bus.publish(
                            "trading.signal",
                            {
                                "symbol": symbol,
                                "signal_type": side,
                                "quantity": amount,
                                "price": entry_price,
                                "source": "thoth_ai",
                                "confidence": confidence,
                                "reasoning": decision.get("reasoning"),
                                "profit_gate_ok": profit_gate_ok,
                                "position_sizing": sizing_meta,
                                "adaptive_policy": adaptive_policy,
                                # SOTA 2025: TP/SL for position monitoring
                                "take_profit_price": tp_sl_data.get("take_profit"),
                                "stop_loss_price": tp_sl_data.get("stop_loss"),
                                "trailing_stop_pct": tp_sl_data.get("trailing_stop_pct"),
                                "asset_class": "crypto",
                            },
                        )

                        price = entry_price
                        if price is not None and price > 0:
                            self._update_symbol_performance(symbol, "crypto", side, price)

                        logger.info(
                            "🤖 Emitted trading.signal from Thoth for %s: %s (conf %.1f)",
                            symbol,
                            side,
                            confidence,
                        )
                    except Exception as sym_err:
                        logger.error(f"Error in crypto auto-trade loop for {symbol}: {sym_err}")

                # Wait before next batch of decisions (risk-tolerance aware)
                await asyncio.sleep(self._get_loop_cycle_delay("crypto"))

        except asyncio.CancelledError:
            logger.info("Crypto auto-trade loop cancelled")
        except Exception as loop_err:
            logger.error(f"Crypto auto-trade loop error: {loop_err}")

    async def _stocks_autotrade_loop(self) -> None:
        """Continuous loop emitting stock.order_submit events for stock symbols."""
        logger.info("🤖 Thoth stocks auto-trade loop started for %s", self.stock_symbols)
        try:
            while self.autonomous_mode and self.stocks_autonomous:
                for symbol in list(self.stock_symbols):
                    try:
                        analysis = await self._analyze_stock_market(symbol)
                        decision = (analysis.get('thoth_decision') or {})
                        action = str(decision.get('action') or '').upper()
                        confidence = float(decision.get('confidence') or 0.0)

                        if action not in ("BUY", "SELL"):
                            continue

                        base = self._get_base_confidence_threshold("stocks")
                        threshold = self._get_symbol_confidence_threshold(
                            symbol, "stocks", base_threshold=base
                        )
                        adaptive_policy = self._derive_adaptive_trade_policy(
                            asset_class="stocks",
                            symbol=symbol,
                            decision=decision,
                            confidence=confidence,
                        )
                        threshold = max(
                            0.0,
                            float(threshold) + float(adaptive_policy.get("threshold_delta", 0.0)),
                        )
                        if confidence < threshold:
                            continue

                        # Profit-focused evaluation using LearningOrchestrator
                        # metrics. We compute whether the profit gate would
                        # allow this trade but we do not block live execution
                        # here; instead we surface the status to the event
                        # payload so Thoth/Ollama can understand what needs to
                        # improve to satisfy the gate.
                        profit_gate_ok = self._profit_gate_allows_live("stocks")
                        if not profit_gate_ok:
                            logger.info(
                                "⚠️ Profit gate would block stocks autotrade for %s (confidence %.1f) but live execution is allowed for learning",
                                symbol,
                                confidence,
                            )
                            if self.event_bus:
                                self.event_bus.publish(
                                    "autotrade.policy.diagnostics",
                                    {
                                        "asset_class": "stocks",
                                        "symbol": symbol,
                                        "profit_gate_ok": False,
                                        "confidence": confidence,
                                        "decision": decision,
                                        "learning_metrics": self.latest_learning_metrics,
                                        "timestamp": datetime.now().isoformat(),
                                    },
                                )

                        if not self.event_bus:
                            continue

                        side = "buy" if action == "BUY" else "sell"

                        # SOTA 2025: Calculate TP/SL for position monitoring
                        entry_price = self._get_current_price(symbol, "stocks")
                        tp_sl_data: Dict[str, Any] = {}
                        if entry_price and entry_price > 0:
                            tp_sl_data = self._calculate_tp_sl_prices(entry_price, side, "stocks")

                        stop_price = tp_sl_data.get("stop_loss") if isinstance(tp_sl_data, dict) else None
                        quantity, sizing_meta = self._compute_trade_size(
                            symbol,
                            asset_class="stocks",
                            side=side,
                            entry_price=entry_price,
                            stop_price=stop_price,
                            confidence=confidence,
                        )
                        quantity = float(quantity) * float(adaptive_policy.get("size_multiplier", 1.0))
                        if quantity <= 0:
                            continue

                        self.event_bus.publish(
                            "stock.order_submit",
                            {
                                "symbol": symbol,
                                "side": side,
                                "type": "market",
                                "quantity": quantity,
                                "price": entry_price,
                                "source": "thoth_ai",
                                "confidence": confidence,
                                "reasoning": decision.get("reasoning"),
                                "profit_gate_ok": profit_gate_ok,
                                "position_sizing": sizing_meta,
                                "adaptive_policy": adaptive_policy,
                                # SOTA 2025: TP/SL for position monitoring
                                "take_profit_price": tp_sl_data.get("take_profit"),
                                "stop_loss_price": tp_sl_data.get("stop_loss"),
                                "trailing_stop_pct": tp_sl_data.get("trailing_stop_pct"),
                                "asset_class": "stocks",
                            },
                        )

                        logger.info(
                            "🤖 Emitted stock.order_submit from Thoth for %s: %s x %.4f (conf %.1f)",
                            symbol,
                            side,
                            quantity,
                            confidence,
                        )
                    except Exception as sym_err:
                        logger.error(f"Error in stocks auto-trade loop for {symbol}: {sym_err}")

                await asyncio.sleep(self._get_loop_cycle_delay("stocks"))

        except asyncio.CancelledError:
            logger.info("Stocks auto-trade loop cancelled")
        except Exception as loop_err:
            logger.error(f"Stocks auto-trade loop error: {loop_err}")
    
    async def _discover_crypto_symbols(self) -> List[str]:
        """Derive crypto/FX symbol universe from API-keyed venues.

        Preference order:
        1) Unified trading.symbol_index published by TradingComponent
        2) RealExchangeExecutor.build_symbol_index() when available
        3) Conservative hardcoded fallback when no live data is reachable
        """
        # 1) Prefer unified symbol index from TradingComponent
        try:
            if isinstance(self.latest_symbol_index, list) and self.latest_symbol_index:
                entries: List[Dict[str, Any]] = []
                for item in self.latest_symbol_index:
                    if not isinstance(item, dict):
                        continue
                    asset = str(item.get("asset_class") or "").lower()
                    if asset not in ("crypto", "fx"):
                        continue
                    entries.append(item)

                if entries:
                    # Sort by popularity descending when available
                    try:
                        entries.sort(
                            key=lambda e: float(e.get("popularity") or 0.0),
                            reverse=True,
                        )
                    except Exception:
                        pass

                    symbols: List[str] = []
                    seen: set[str] = set()
                    for e in entries:
                        sym = str(e.get("symbol") or "").upper()
                        if not sym or sym in seen:
                            continue
                        seen.add(sym)
                        symbols.append(sym)

                    if symbols:
                        # Cap to a reasonable universe to avoid over-trading
                        return symbols[:100]
        except Exception as e:
            logger.error(f"Error deriving crypto symbols from trading.symbol_index: {e}")

        # 2) Fall back to asking RealExchangeExecutor directly
        try:
            if self.real_exchange_executor is not None:
                index = await self.real_exchange_executor.build_symbol_index()
                entries2: List[Dict[str, Any]] = []
                for item in index:
                    if not isinstance(item, dict):
                        continue
                    asset = str(item.get("asset_class") or "").lower()
                    if asset not in ("crypto", "fx"):
                        continue
                    entries2.append(item)

                if entries2:
                    try:
                        entries2.sort(
                            key=lambda e: float(e.get("popularity") or 0.0),
                            reverse=True,
                        )
                    except Exception:
                        pass

                    symbols2: List[str] = []
                    seen2: set[str] = set()
                    for e in entries2:
                        sym = str(e.get("symbol") or "").upper()
                        if not sym or sym in seen2:
                            continue
                        seen2.add(sym)
                        symbols2.append(sym)

                    if symbols2:
                        return symbols2[:100]
        except Exception as e:
            logger.error(f"Error deriving crypto symbols from RealExchangeExecutor: {e}")

        # 3) Extremely conservative default when no live data is available
        return ["BTC/USDT", "ETH/USDT"]

    async def _discover_stock_symbols(self) -> List[str]:
        """Derive stock symbol universe from API-keyed brokers.

        This relies on the unified trading.symbol_index published by
        TradingComponent, which in turn uses RealStockExecutor to
        discover tradable assets from configured brokers (e.g. Alpaca).
        """
        try:
            if isinstance(self.latest_symbol_index, list) and self.latest_symbol_index:
                entries: List[Dict[str, Any]] = []
                for item in self.latest_symbol_index:
                    if not isinstance(item, dict):
                        continue
                    asset = str(item.get("asset_class") or "").lower()
                    if asset != "stock":
                        continue
                    entries.append(item)

                if entries:
                    try:
                        entries.sort(
                            key=lambda e: float(e.get("popularity") or 0.0),
                            reverse=True,
                        )
                    except Exception:
                        pass

                    symbols: List[str] = []
                    seen: set[str] = set()
                    for e in entries:
                        sym = str(e.get("symbol") or "").upper()
                        if not sym or sym in seen:
                            continue
                        seen.add(sym)
                        symbols.append(sym)

                    if symbols:
                        # Limit to a focused universe of most liquid names
                        return symbols[:100]
        except Exception as e:
            logger.error(f"Error deriving stock symbols from trading.symbol_index: {e}")

        # Fallback when no symbol index is available at all
        return ["AAPL"]

    def _get_symbol_performance_key(self, symbol: str, asset_class: str) -> str:
        return f"{asset_class}:{symbol}".upper()

    def _get_rl_sizing_policy(self) -> Optional[ConservativeSizingPolicy]:
        """Lazily construct an RL-informed sizing policy if possible.

        This consults the OnlineRLTrainer backend via the EventBus component
        registry and, when available, wraps its Q-network in a
        ConservativeSizingPolicy. If anything fails, sizing falls back to the
        conservative max_trade_size_usd logic.
        """

        if self._rl_sizing_policy is not None:
            return self._rl_sizing_policy

        eb = getattr(self, "event_bus", None)
        if eb is None or not hasattr(eb, "get_component"):
            return None

        try:
            trainer = eb.get_component("online_rl_trainer")
        except Exception:
            trainer = None
        if trainer is None:
            return None

        try:
            adapter_fn = getattr(trainer, "get_q_estimator_adapter", None)
            if not callable(adapter_fn):
                return None
            q_est = adapter_fn()
            if q_est is None:
                return None

            policy = ConservativeSizingPolicy(
                config={
                    "cvar_alpha": 0.05,
                    "cql_penalty": 1.0,
                    "max_fraction": 0.05,
                    "min_fraction": 0.0,
                }
            )
            policy.load_q_estimator(q_est)
            self._rl_sizing_policy = policy
            return policy
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error constructing RL sizing policy: {e}")
            return None

    def _build_rl_sizing_state(self, asset_class: str) -> Optional[Dict[str, float]]:
        """Build a compact state dict for RL sizing from paper metrics.

        The state keys are aligned with ConservativeSizingPolicy and the
        OnlineRLTrainer feature space:

            - recent_volatility
            - recent_drawdown_pct
            - win_rate
            - edge_estimate
        """

        pm = getattr(self, "latest_paper_metrics", None)
        if not isinstance(pm, dict):
            return None

        try:
            trades = int(pm.get("trade_count", 0) or 0)
            wins = int(pm.get("wins", 0) or 0)
            losses = int(pm.get("losses", 0) or 0)
            total = max(1, wins + losses)
            win_rate = wins / float(total)

            max_dd = float(pm.get("max_drawdown", 0.0) or 0.0)
            avg_trade_return = float(pm.get("avg_trade_return", 0.0) or 0.0)
            recent_vol = float(pm.get("recent_volatility", 0.0) or 0.0)
            if recent_vol <= 0.0:
                recent_vol = max(1e-6, abs(avg_trade_return))

            return {
                "recent_volatility": recent_vol,
                "recent_drawdown_pct": max_dd,
                "win_rate": win_rate,
                "edge_estimate": avg_trade_return,
            }
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error building RL sizing state for {asset_class}: {e}")
            return None

    def _get_base_confidence_threshold(self, asset_class: str) -> float:
        """Derive a base confidence threshold from global risk_tolerance.

        High risk → lower thresholds (more trades).
        Low risk  → higher thresholds (fewer, higher-conviction trades).
        """
        rt = (self.risk_tolerance or "medium").lower()

        # PREDATOR MODE: aggressively lower confidence gating.
        if self._is_predator_mode():
            return 25.0

        if asset_class == "crypto":
            if rt == "high":
                return 55.0
            if rt == "low":
                return 85.0
            return 70.0
        # Stocks: slightly more conservative by default
        if rt == "high":
            return 60.0
        if rt == "low":
            return 85.0
        return 75.0

    def _get_loop_cycle_delay(self, asset_class: str) -> float:
        """Determine how quickly each auto-trade loop should cycle.

        Higher risk → shorter delays (more frequent decisions).
        Lower risk  → longer delays (more patient trading).
        """
        rt = (self.risk_tolerance or "medium").lower()

        # PREDATOR MODE: cycle faster to hunt opportunities.
        if self._is_predator_mode():
            return 5.0 if asset_class == "crypto" else 15.0

        if asset_class == "crypto":
            if rt == "high":
                return 10.0
            if rt == "low":
                return 120.0
            return 45.0
        # stocks
        if rt == "high":
            return 45.0
        if rt == "low":
            return 240.0
        return 90.0

    def _get_symbol_confidence_threshold(self, symbol: str, asset_class: str, base_threshold: float) -> float:
        # PREDATOR MODE: keep per-symbol gating but clamp to a low ceiling.
        if self._is_predator_mode():
            try:
                base = float(base_threshold)
            except Exception:
                base = 25.0
            return max(15.0, min(35.0, base))

        key = self._get_symbol_performance_key(symbol, asset_class)
        stats = self.symbol_performance.get(key)
        if not isinstance(stats, dict):
            return float(base_threshold)

        trades = int(stats.get("trades") or 0)
        if trades < 5:
            return float(base_threshold)

        wins = int(stats.get("wins") or 0)
        if trades <= 0:
            return float(base_threshold)

        win_rate = wins / float(trades)
        threshold = float(base_threshold)

        if win_rate >= 0.65:
            threshold = max(50.0, base_threshold - 10.0)
        elif win_rate <= 0.35:
            threshold = min(90.0, base_threshold + 10.0)

        return float(threshold)

    def _calculate_tp_sl_prices(
        self, current_price: float, side: str, asset_class: str
    ) -> Dict[str, Optional[float]]:
        """
        SOTA 2025: Calculate Take Profit and Stop Loss prices based on risk tolerance.
        
        Returns dict with 'take_profit', 'stop_loss', 'trailing_stop_pct' keys.
        """
        # Risk-tolerance based TP/SL percentages
        risk_config = {
            'low': {'tp_pct': 0.015, 'sl_pct': 0.008, 'trailing_pct': 0.012},    # 1.5% TP, 0.8% SL
            'medium': {'tp_pct': 0.025, 'sl_pct': 0.015, 'trailing_pct': 0.018}, # 2.5% TP, 1.5% SL
            'high': {'tp_pct': 0.05, 'sl_pct': 0.025, 'trailing_pct': 0.03},     # 5% TP, 2.5% SL
        }

        # PREDATOR MODE: wider bands (more room to breathe) + more reward seeking.
        if self._is_predator_mode():
            risk_config["predator"] = {
                "tp_pct": 0.10,
                "sl_pct": 0.05,
                "trailing_pct": 0.06,
            }
        
        # Asset-class adjustments (crypto more volatile)
        volatility_mult = 1.5 if asset_class == 'crypto' else 1.0
        
        rt_key = "predator" if self._is_predator_mode() else self.risk_tolerance
        config = risk_config.get(rt_key, risk_config['medium'])
        tp_pct = config['tp_pct'] * volatility_mult
        sl_pct = config['sl_pct'] * volatility_mult
        trailing_pct = config['trailing_pct'] * volatility_mult
        
        if side.lower() in ('buy', 'long'):
            take_profit = current_price * (1 + tp_pct)
            stop_loss = current_price * (1 - sl_pct)
        else:  # sell/short
            take_profit = current_price * (1 - tp_pct)
            stop_loss = current_price * (1 + sl_pct)
        
        return {
            'take_profit': round(take_profit, 8),
            'stop_loss': round(stop_loss, 8),
            'trailing_stop_pct': trailing_pct,
        }

    def _get_current_price(self, symbol: str, asset_class: str) -> Optional[float]:
        price: Optional[float] = None

        try:
            if asset_class == "crypto" and self.live_trades_feed is not None:
                raw = self.live_trades_feed.get_last_price(symbol)
                if raw is not None:
                    price = float(raw)
        except Exception:
            price = None

        if price is not None and price > 0:
            return price

        try:
            if asset_class == "stocks" and isinstance(self.latest_portfolio_snapshot, dict):
                stocks = self.latest_portfolio_snapshot.get("stocks") or self.latest_portfolio_snapshot.get("stock_positions")
                if isinstance(stocks, list):
                    sym_upper = symbol.upper()
                    for pos in stocks:
                        if not isinstance(pos, dict):
                            continue
                        if str(pos.get("symbol") or "").upper() != sym_upper:
                            continue
                        cand = pos.get("price") or pos.get("current_price") or pos.get("avg_price")
                        if cand is not None:
                            return float(cand)
        except Exception:
            return None

        return None

    def _update_symbol_performance(self, symbol: str, asset_class: str, side: str, price: float) -> None:
        if price <= 0:
            return

        key = self._get_symbol_performance_key(symbol, asset_class)
        stats = self.symbol_performance.get(key)
        if not isinstance(stats, dict):
            stats = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "realized_return": 0.0,
                "avg_return": 0.0,
                "last_side": None,
                "last_entry_price": None,
            }

        last_side = stats.get("last_side")
        last_entry = stats.get("last_entry_price")

        if isinstance(last_side, str) and isinstance(last_entry, (int, float)) and float(last_entry) > 0:
            prev_side = last_side.lower()
            curr_side = side.lower()
            if curr_side in ("buy", "sell") and prev_side in ("buy", "sell") and curr_side != prev_side:
                if prev_side == "buy":
                    ret = (price - float(last_entry)) / float(last_entry)
                else:
                    ret = (float(last_entry) - price) / float(last_entry)

                trades = int(stats.get("trades") or 0) + 1
                wins = int(stats.get("wins") or 0)
                losses = int(stats.get("losses") or 0)

                if ret > 0:
                    wins += 1
                elif ret < 0:
                    losses += 1

                realized = float(stats.get("realized_return") or 0.0) + float(ret)
                avg_ret = realized / float(trades) if trades > 0 else 0.0

                stats["trades"] = trades
                stats["wins"] = wins
                stats["losses"] = losses
                stats["realized_return"] = realized
                stats["avg_return"] = avg_ret

        stats["last_side"] = side
        stats["last_entry_price"] = float(price)
        self.symbol_performance[key] = stats

    def _build_symbol_performance_view(self, symbol: str, asset_class: str) -> Optional[Dict[str, Any]]:
        """Summarize per-symbol performance for use in prompts.

        Returns a compact dict focused on the requested symbol and asset_class,
        or None when no history exists yet.
        """
        try:
            key = self._get_symbol_performance_key(symbol, asset_class)
            stats = self.symbol_performance.get(key)
            if not isinstance(stats, dict):
                return None

            trades = int(stats.get("trades") or 0)
            wins = int(stats.get("wins") or 0)
            losses = int(stats.get("losses") or 0)
            realized = float(stats.get("realized_return") or 0.0)
            avg_ret = float(stats.get("avg_return") or 0.0)
            win_rate = (float(wins) / float(trades)) if trades > 0 else 0.0

            return {
                "asset_class": asset_class,
                "symbol": symbol,
                "trades": trades,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "realized_return": realized,
                "avg_return": avg_ret,
                "last_side": stats.get("last_side"),
                "last_entry_price": stats.get("last_entry_price"),
            }
        except Exception:
            return None

    def _build_strategy_marketplace_view(self) -> Optional[Dict[str, Any]]:
        """Summarize Strategy Marketplace performance for prompts.

        Uses the latest trading.strategy_marketplace.snapshot to surface the
        strongest strategy categories and top strategies by win_rate and
        profit_factor, without altering any marketplace logic.
        """
        snap = self.latest_strategy_marketplace_snapshot
        if not isinstance(snap, dict):
            return None

        strategies = snap.get("strategies")
        if not isinstance(strategies, list) or not strategies:
            return None

        # Build a small list of top strategies by combined score
        try:
            sorted_strats = sorted(
                [s for s in strategies if isinstance(s, dict)],
                key=lambda s: (
                    float(s.get("win_rate") or 0.0) * 2.0
                    + float(s.get("profit_factor") or 0.0)
                    + float(s.get("avg_rating") or 0.0)
                ),
                reverse=True,
            )
        except Exception:
            sorted_strats = [s for s in strategies if isinstance(s, dict)]

        top_strategies: List[Dict[str, Any]] = []
        for s in sorted_strats[:10]:
            try:
                entry: Dict[str, Any] = {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "category": s.get("category"),
                    "risk_level": s.get("risk_level"),
                    "avg_rating": float(s.get("avg_rating") or 0.0),
                    "subscribers": int(s.get("subscribers") or 0),
                }
                for key in ("win_rate", "profit_factor", "sharpe_ratio", "max_drawdown"):
                    val = s.get(key)
                    if isinstance(val, (int, float)):
                        entry[key] = float(val)
                top_strategies.append(entry)
            except Exception:
                continue

        # Aggregate simple category-level stats
        category_stats: Dict[str, Dict[str, Any]] = {}
        for s in strategies:
            if not isinstance(s, dict):
                continue
            cat = str(s.get("category") or "").strip()
            if not cat:
                continue
            bucket = category_stats.setdefault(
                cat,
                {
                    "strategies": 0,
                    "win_rate_sum": 0.0,
                    "win_rate_n": 0,
                    "profit_factor_sum": 0.0,
                    "profit_factor_n": 0,
                    "subscribers": 0,
                },
            )
            bucket["strategies"] += 1

            wr = s.get("win_rate")
            if isinstance(wr, (int, float)):
                bucket["win_rate_sum"] += float(wr)
                bucket["win_rate_n"] += 1

            pf = s.get("profit_factor")
            if isinstance(pf, (int, float)):
                bucket["profit_factor_sum"] += float(pf)
                bucket["profit_factor_n"] += 1

            subs = s.get("subscribers")
            if isinstance(subs, int):
                bucket["subscribers"] += subs

        cat_view: Dict[str, Any] = {}
        for cat, agg in category_stats.items():
            try:
                wr_n = agg.get("win_rate_n") or 0
                pf_n = agg.get("profit_factor_n") or 0
                cat_view[cat] = {
                    "strategies": int(agg.get("strategies") or 0),
                    "avg_win_rate": (
                        float(agg.get("win_rate_sum") or 0.0) / float(wr_n)
                        if wr_n > 0
                        else None
                    ),
                    "avg_profit_factor": (
                        float(agg.get("profit_factor_sum") or 0.0) / float(pf_n)
                        if pf_n > 0
                        else None
                    ),
                    "total_subscribers": int(agg.get("subscribers") or 0),
                }
            except Exception:
                continue

        try:
            summary = snap.get("summary") or {}
        except Exception:
            summary = {}

        return {
            "timestamp": snap.get("timestamp"),
            "strategy_count": snap.get("strategy_count"),
            "total_subscriptions": summary.get("total_subscriptions"),
            "top_strategies": top_strategies,
            "category_stats": cat_view,
        }

    async def _build_global_autotrade_plan(
        self,
        crypto_symbols: List[str],
        stock_symbols: List[str],
    ) -> Dict[str, Any]:
        """Aggregate past + present data into a global auto-trading plan.

        This is used by ai.autotrade.analyze_and_start to explain how Thoth
        intends to trade across ALL API-keyed venues before the loops start as
        a single, multi-asset global universe (crypto + stocks).
        """

        merged_universe: List[str] = sorted(
            {s.upper() for s in crypto_symbols} | {s.upper() for s in stock_symbols}
        )

        plan: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "risk_tolerance": self.risk_tolerance,
            "max_trade_size_usd": float(self.max_trade_size_usd),
            "crypto_universe_size": len(crypto_symbols),
            "stock_universe_size": len(stock_symbols),
            "crypto_universe_sample": crypto_symbols[:50],
            "stock_universe_sample": stock_symbols[:50],
            # Multi-asset, cross-venue view of the entire tradable universe
            "global_universe_size": len(merged_universe),
            "global_universe_sample": merged_universe[:100],
        }

        # Venue / broker universe derived from API-keyed connectors
        venues: List[Dict[str, Any]] = []
        try:
            if isinstance(self.latest_exchange_health_snapshot, dict):
                h = self.latest_exchange_health_snapshot.get("health")
                if isinstance(h, dict):
                    for name, info in h.items():
                        if not isinstance(info, dict):
                            continue
                        venues.append(
                            {
                                "type": "exchange",
                                "name": str(name),
                                "status": str(info.get("status") or ""),
                            }
                        )
        except Exception as e:
            logger.error(f"Error summarizing exchange health for plan: {e}")

        try:
            if isinstance(self.latest_stock_broker_health_snapshot, dict):
                h2 = self.latest_stock_broker_health_snapshot.get("health")
                if isinstance(h2, dict):
                    for name, info in h2.items():
                        if not isinstance(info, dict):
                            continue
                        venues.append(
                            {
                                "type": "broker",
                                "name": str(name),
                                "status": str(info.get("status") or ""),
                            }
                        )
        except Exception as e:
            logger.error(f"Error summarizing stock broker health for plan: {e}")

        plan["venues"] = venues
        plan["venue_count"] = len(venues)

        # Past performance over all traded symbols (crypto + stocks)
        crypto_set = {s.upper() for s in crypto_symbols}
        stock_set = {s.upper() for s in stock_symbols}
        top_crypto: List[Dict[str, Any]] = []
        top_stocks: List[Dict[str, Any]] = []

        for key, stats in self.symbol_performance.items():
            if not isinstance(stats, dict):
                continue
            try:
                asset, sym = key.split(":", 1)
            except ValueError:
                continue
            asset = asset.lower()
            sym_u = sym.upper()

            trades = int(stats.get("trades") or 0)
            wins = int(stats.get("wins") or 0)
            realized = float(stats.get("realized_return") or 0.0)
            avg_ret = float(stats.get("avg_return") or 0.0)
            win_rate = (float(wins) / float(trades)) if trades > 0 else 0.0

            entry = {
                "asset_class": asset,
                "symbol": sym_u,
                "trades": trades,
                "wins": wins,
                "realized_return": realized,
                "avg_return": avg_ret,
                "win_rate": win_rate,
            }

            if asset in ("crypto", "fx") and sym_u in crypto_set:
                top_crypto.append(entry)
            elif asset == "stocks" and sym_u in stock_set:
                top_stocks.append(entry)

        def _sort_perf(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            try:
                return sorted(
                    entries,
                    key=lambda e: (
                        float(e.get("avg_return") or 0.0),
                        float(e.get("win_rate") or 0.0),
                    ),
                    reverse=True,
                )
            except Exception:
                return entries

        top_crypto = _sort_perf(top_crypto)[:20]
        top_stocks = _sort_perf(top_stocks)[:20]
        plan["top_crypto_symbols"] = top_crypto
        plan["top_stock_symbols"] = top_stocks

        # Strategy Marketplace and risk/portfolio context
        strat_view = self._build_strategy_marketplace_view()
        if strat_view is not None:
            plan["strategy_marketplace"] = strat_view

        if self.latest_portfolio_snapshot is not None:
            plan["portfolio_snapshot"] = self.latest_portfolio_snapshot
        if self.latest_risk_snapshot is not None:
            plan["risk_snapshot_latest"] = self.latest_risk_snapshot
        if self.latest_arbitrage_snapshot is not None:
            plan["arbitrage_snapshot_latest"] = self.latest_arbitrage_snapshot

        # If Ollama is online, let it synthesize a high-level, cross-market
        # trading plan using this aggregated context.
        if self.ollama_available:
            try:
                thoth_plan = await self._query_ollama_global_plan(plan)
                if isinstance(thoth_plan, dict):
                    plan["thoth_global_plan"] = thoth_plan
            except Exception as e:
                logger.error(f"Error querying Ollama for global plan: {e}")

        return plan

    async def _query_ollama_global_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ask Ollama/Thoth to design a global auto-trading plan.

        The model sees ALL API-keyed venues, symbol universes, past performance,
        and strategy marketplace performance, and returns a JSON plan describing
        how to trade crypto and stocks for maximum expected profitability within
        the configured risk_tolerance and max_trade_size_usd. It should treat
        ALL discovered symbols across ALL healthy venues as a single multi-asset
        portfolio it can trade simultaneously (no per-asset restriction beyond
        risk controls).
        """
        try:
            import aiohttp
            import json

            prompt = f"""You are Kingdom AI, a 2025 state-of-the-art autonomous MULTI-ASSET trading brain.

You control REAL cryptocurrency exchanges and stock brokers via API keys.
You may trade ANY symbol in the provided universes on ANY healthy venue, and
you may hold and trade MANY assets and venues SIMULTANEOUSLY to maximize
profitability, compound returns, and accumulate high-quality assets over time.

You receive the following GLOBAL auto-trading context as JSON:

{json.dumps(context, indent=2)}

Design a high-level trading plan that maximizes expected, RISK-ADJUSTED
profitability across ALL markets (crypto + stocks) while respecting the
configured risk_tolerance and max_trade_size_usd. Think in terms of a global
portfolio:
- You are NOT restricted to any single symbol or venue.
- You can rotate capital dynamically across symbols, asset classes, and venues.
- You can trade concurrently on multiple exchanges/brokers when profitable.
- You should favor compounding and long-term asset accumulation, not just
  single isolated trades.

You should:
- Focus on symbols and strategies with strong historical win_rate and
  realized_return.
- Prefer strategy categories with solid avg_win_rate and profit_factor.
- Respect portfolio/risk constraints from the risk snapshot.

Respond ONLY in this JSON format (you may extend notes/strings but NOT the
top-level keys):
{{
  "overall_thesis": "short English summary of the global multi-asset plan",
  "crypto_plan": {{
    "focus_symbols": ["BTC/USDT", "ETH/USDT", ...],
    "style": "scalping/swing/trend/arbitrage mix",
    "notes": "how you intend to trade crypto across ALL connected exchanges"
  }},
  "stocks_plan": {{
    "focus_symbols": ["AAPL", "TSLA", ...],
    "style": "swing/position/intraday",
    "notes": "how you intend to trade stocks across ALL connected brokers"
  }},
  "risk_management": "how you will avoid catastrophic loss while still
                       compounding capital across many positions",
  "trade_frequency": "how often you expect to trade (high/medium/low)"
}}"""

            try:
                from core.ollama_gateway import orchestrator
                _plan_model = orchestrator.get_model_for_task("trading")
            except ImportError:
                _plan_model = self.current_model or "cogito:latest"

            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": _plan_model,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": -1,
                    "options": {"num_gpu": 999},
                }

                try:
                    from core.ollama_gateway import get_ollama_url
                    _orch_base3 = get_ollama_url()
                except ImportError:
                    _orch_base3 = "http://localhost:11434"
                base = getattr(self, "_ollama_base", _orch_base3)
                async with session.post(f"{base.rstrip('/')}/api/generate", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        text = result.get("response", "{}")
                        try:
                            return json.loads(text)
                        except Exception:
                            return {
                                "overall_thesis": "Hold mode: global plan could not be parsed.",
                                "crypto_plan": {},
                                "stocks_plan": {},
                                "risk_management": "Fallback: use internal risk manager only.",
                                "trade_frequency": "medium",
                            }

            return {
                "overall_thesis": "Hold mode: Ollama global plan query failed.",
                "crypto_plan": {},
                "stocks_plan": {},
                "risk_management": "Fallback: use internal risk manager only.",
                "trade_frequency": "medium",
            }

        except Exception as e:
            logger.error(f"Error querying Ollama for global auto-trade plan: {e}")
            return {
                "overall_thesis": f"Error building global plan: {e}",
                "crypto_plan": {},
                "stocks_plan": {},
                "risk_management": "Fallback: use internal risk manager only.",
                "trade_frequency": "medium",
            }

    def enable_autonomous_mode(
        self,
        max_trade_size_usd: float = 1000.0,
        risk_tolerance: str = 'medium'
    ):
        """
        Enable Thoth autonomous trading mode.
        
        Args:
            max_trade_size_usd: Maximum trade size in USD
            risk_tolerance: Risk tolerance level
        """
        self.autonomous_mode = True
        self.max_trade_size_usd = max_trade_size_usd
        self.risk_tolerance = risk_tolerance
        
        logger.info(f"✅ Thoth autonomous mode ENABLED")
        logger.info(f"   Max trade size: ${max_trade_size_usd}")
        logger.info(f"   Risk tolerance: {risk_tolerance}")
    
    def disable_autonomous_mode(self):
        """Disable Thoth autonomous trading mode."""
        self.autonomous_mode = False
        logger.info("❌ Thoth autonomous mode DISABLED")

    def _compute_trade_size(
        self,
        symbol: str,
        asset_class: str,
        side: str,
        entry_price: Optional[float],
        stop_price: Optional[float],
        confidence: Optional[float],
    ) -> Tuple[float, Dict[str, Any]]:
        price = 0.0
        if entry_price is not None:
            try:
                price = float(entry_price)
            except (TypeError, ValueError):
                price = 0.0

        if price <= 0.0:
            try:
                observed = self._get_current_price(symbol, asset_class)
                if observed is not None:
                    price = float(observed)
            except Exception:
                price = 0.0

        if price <= 0.0:
            price = 100.0 if asset_class == "stocks" else 50.0

        max_notional = float(getattr(self, "max_trade_size_usd", 0.0) or 0.0)
        if max_notional <= 0.0:
            return 0.0, {}

        equity = 0.0
        try:
            ps = getattr(self, "latest_portfolio_snapshot", None)
            if isinstance(ps, dict):
                equity = float(ps.get("total_usd") or 0.0)
        except Exception:
            equity = 0.0
        if equity <= 0.0:
            equity = max_notional

        drawdown_pct: Optional[float] = None
        try:
            rs = getattr(self, "latest_risk_snapshot", None)
            if isinstance(rs, dict):
                cand = rs.get("max_drawdown")
                if cand is None:
                    cand = rs.get("max_drawdown_pct")
                if cand is not None:
                    drawdown_pct = float(cand)
        except Exception:
            drawdown_pct = None

        volatility: Optional[float] = None
        avg_volatility: Optional[float] = None
        try:
            vol, avg_vol = self._estimate_volatility(symbol)
            volatility = vol
            avg_volatility = avg_vol
        except Exception:
            volatility = None
            avg_volatility = None

        base_risk_fraction = self._base_risk_fraction(asset_class)
        risk_fraction = float(base_risk_fraction)

        # PREDATOR MODE: amplify risk fraction further with confidence.
        if self._is_predator_mode():
            try:
                conf_val = float(confidence) if confidence is not None else 0.0
            except Exception:
                conf_val = 0.0
            # confidence is typically 0-100; map to [1.0, 2.0]
            conf_mult = 1.0 + max(0.0, min(1.0, conf_val / 100.0))
            risk_fraction = min(0.10, risk_fraction * conf_mult)

        stop_distance_for_sizing: Optional[float] = None
        if stop_price is not None:
            try:
                stop_distance_for_sizing = abs(float(price) - float(stop_price))
            except (TypeError, ValueError):
                stop_distance_for_sizing = None

        if (
            stop_distance_for_sizing is not None
            and stop_distance_for_sizing > 0.0
            and equity > 0.0
            and price > 0.0
            and max_notional > 0.0
        ):
            # Choose a risk fraction that would yield the max_notional position
            # size when multipliers are neutral. This allows confidence/
            # drawdown/volatility multipliers (and Kelly/RL caps) to scale the
            # final notional *below* the hard max_notional cap.
            cap_risk_fraction = (max_notional * stop_distance_for_sizing) / (equity * price)
            if cap_risk_fraction > 0.0:
                risk_fraction = min(risk_fraction, float(cap_risk_fraction))

        kelly_fraction: Optional[float] = None
        suggested_fraction: Optional[float] = None
        try:
            metrics = getattr(self, "latest_learning_metrics", None) or {}
            if isinstance(metrics, dict):
                profit_view = metrics.get("paper_profit_view") or metrics.get("paper_profit") or {}
                if isinstance(profit_view, dict):
                    sizing = profit_view.get("sizing") or {}
                    if isinstance(sizing, dict):
                        kf_val = sizing.get("kelly_fraction")
                        if kf_val is not None:
                            try:
                                kelly_fraction = float(kf_val)
                            except (TypeError, ValueError):
                                kelly_fraction = None

                        sf_val = sizing.get("suggested_fraction")
                        if sf_val is not None:
                            try:
                                suggested_fraction = float(sf_val)
                            except (TypeError, ValueError):
                                suggested_fraction = None
        except Exception:
            kelly_fraction = None
            suggested_fraction = None

        rl_fraction: Optional[float] = None
        try:
            policy = self._get_rl_sizing_policy()
            if policy is not None:
                state = self._build_rl_sizing_state(asset_class)
                if state is not None:
                    rl_fraction = float(policy.suggested_fraction(state))
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error deriving RL sizing fraction for {symbol}: {e}")
            rl_fraction = None

        qty_step: Optional[float] = 1.0 if asset_class == "stocks" else None

        inputs = PositionSizingInputs(
            equity_usd=float(equity),
            entry_price=float(price),
            stop_price=float(stop_price) if stop_price is not None else None,
            risk_fraction=float(risk_fraction),
            side=str(side),
            confidence=float(confidence) if confidence is not None else None,
            max_notional_usd=float(max_notional),
            drawdown_pct=drawdown_pct,
            volatility=volatility,
            avg_volatility=avg_volatility,
            kelly_fraction=kelly_fraction,
            rl_fraction=rl_fraction,
            qty_step=qty_step,
            min_qty=0.0,
            extra={
                "asset_class": asset_class,
                "symbol": symbol,
                "risk_tolerance": getattr(self, "risk_tolerance", None),
                "predator_mode": self._is_predator_mode(),
                "predator_mode_source": getattr(self, "predator_mode_source", None),
                "kelly_suggested_fraction": suggested_fraction,
                "base_risk_fraction": base_risk_fraction,
            },
        )

        result = self._position_sizer.size(inputs)

        meta: Dict[str, Any] = {
            "engine": "PositionSizer",
            "inputs": asdict(inputs),
            "result": asdict(result),
        }
        return float(result.quantity), meta

    def _base_risk_fraction(self, asset_class: str) -> float:
        rt = str(getattr(self, "risk_tolerance", "medium") or "medium").lower()
        if self._is_predator_mode():
            # PREDATOR MODE: larger base risk budget. Hard cap still enforced by max_notional.
            return 0.05 if asset_class == "crypto" else 0.03
        if rt == "low":
            return 0.005
        if rt == "high":
            return 0.02 if asset_class == "stocks" else 0.03
        return 0.01

    def _estimate_volatility(self, symbol: str) -> Tuple[Optional[float], Optional[float]]:
        if self.live_price_charts is None:
            return None, None
        ohlcv = self.live_price_charts.get_chart_data(symbol)
        if not ohlcv or len(ohlcv) < 20:
            return None, None

        closes: List[float] = []
        for candle in ohlcv:
            try:
                closes.append(float(candle[4]))
            except Exception:
                continue
        if len(closes) < 20:
            return None, None

        arr = np.asarray(closes, dtype=float)
        rets = np.diff(arr) / np.maximum(arr[:-1], 1e-12)
        if rets.size < 5:
            return None, None

        cur_window = int(min(30, rets.size))
        long_window = int(min(120, rets.size))

        cur = float(np.std(rets[-cur_window:])) if cur_window > 1 else None
        avg = float(np.std(rets[-long_window:])) if long_window > 1 else None
        return cur, avg
    
    async def thoth_query(self, user_query: str) -> str:
        """
        User queries Thoth AI brain - can execute ANY task across ALL systems.
        
        Args:
            user_query: User's question or command
            
        Returns:
            Thoth's response
        """
        try:
            # First, check if this is an executable command
            command_result = await self.execute_user_command(user_query)
            if command_result.get("executed"):
                return command_result.get("response", "Command executed successfully")
            
            # If not a command, use neural orchestration for analysis
            if self.ollama_available and self.neural_mode_enabled:
                task = NeuralTask(
                    task_id=f"query_{datetime.now().timestamp()}",
                    task_type="general",
                    prompt=user_query,
                    context=self._get_current_system_context(),
                    priority=5
                )
                result = await self.neural_orchestrator.process_task_neural(task)
                consensus = result.get("consensus", {})
                if isinstance(consensus, dict):
                    return consensus.get("synthesized", consensus.get("text", str(consensus)))
                return str(consensus)
            
            if self.ollama_available:
                import aiohttp
                try:
                    from core.ollama_gateway import orchestrator
                    _query_model = orchestrator.get_model_for_task("trading")
                except ImportError:
                    _query_model = self.current_model or "cogito:latest"
                try:
                    from core.ollama_gateway import get_ollama_url
                    _orch_base4 = get_ollama_url()
                except ImportError:
                    _orch_base4 = "http://localhost:11434"
                base = getattr(self, "_ollama_base", _orch_base4)
                async with aiohttp.ClientSession() as session:
                    payload = {
                        'model': _query_model,
                        'prompt': f"""You are Kingdom AI, a cryptocurrency trading assistant with access to real-time market data. 

User Query: {user_query}

Provide a helpful, accurate response based on real market data and trading principles.""",
                        'stream': False,
                        'keep_alive': -1,
                        'options': {'num_gpu': 999},
                    }
                    
                    async with session.post(f'{base.rstrip("/")}/api/generate', json=payload) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result.get('response', 'No response from Ollama')
            
            return "Thoth AI is currently offline. Please start Ollama to enable AI features."
            
        except Exception as e:
            logger.error(f"Error in Thoth query: {e}")
            return f"Error: {str(e)}"

    def _get_current_system_context(self) -> Dict[str, Any]:
        """Get current context from all live systems for Thoth."""
        context = {
            "timestamp": datetime.now().isoformat(),
            "autonomous_mode": getattr(self, "autonomous_mode", False),
            "max_trade_size_usd": getattr(self, "max_trade_size_usd", 1000.0),
            "risk_tolerance": getattr(self, "risk_tolerance", "medium"),
        }
        
        # Add latest snapshots if available
        if hasattr(self, "latest_portfolio_snapshot"):
            context["portfolio"] = self.latest_portfolio_snapshot
        if hasattr(self, "latest_risk_snapshot"):
            context["risk"] = self.latest_risk_snapshot
        if hasattr(self, "latest_exchange_health_snapshot"):
            context["exchange_health"] = self.latest_exchange_health_snapshot
        if hasattr(self, "latest_arbitrage_snapshot"):
            context["arbitrage"] = self.latest_arbitrage_snapshot
        if hasattr(self, "latest_anomaly_snapshot"):
            context["anomaly"] = self.latest_anomaly_snapshot

        # Vision system context (webcam / passthrough view)
        if getattr(self, "latest_vision_analysis", None) is not None:
            context["vision"] = self.latest_vision_analysis

        # VR world model context (headset session, tracking, interactions, designs)
        vr_ctx: Dict[str, Any] = {}

        # Session state and high-level VR status
        if getattr(self, "vr_session_state", None):
            vr_ctx["session"] = self.vr_session_state
        if getattr(self, "latest_vr_status", None):
            vr_ctx["status"] = self.latest_vr_status

        # Headset tracking summary
        if getattr(self, "latest_vr_tracking", None):
            vr_ctx["tracking"] = self.latest_vr_tracking

        # Performance telemetry (FPS / frame time / drops)
        if getattr(self, "latest_vr_performance", None):
            vr_ctx["performance"] = self.latest_vr_performance

        # Sentience metrics computed from VR data
        if getattr(self, "latest_vr_sentience_metrics", None):
            vr_ctx["sentience_metrics"] = self.latest_vr_sentience_metrics

        # Latest interaction (what the user just did in VR)
        if getattr(self, "latest_vr_interaction", None):
            vr_ctx["latest_interaction"] = self.latest_vr_interaction

        # Active VR designs (objects the brain has created or is manipulating)
        active_designs = getattr(self, "active_vr_designs", None)
        if isinstance(active_designs, dict) and active_designs:
            summarized_designs: Dict[str, Any] = {}
            for design_id, data in active_designs.items():
                try:
                    spec = data.get("spec") if isinstance(data, dict) else {}
                    summarized_designs[design_id] = {
                        "name": data.get("name"),
                        "position": data.get("position") or (spec.get("position") if isinstance(spec, dict) else None),
                        "rotation": data.get("rotation") or (spec.get("rotation") if isinstance(spec, dict) else None),
                    }
                except Exception:
                    continue
            if summarized_designs:
                vr_ctx["designs"] = summarized_designs

        # Recent high-level VR actions for temporal context
        if getattr(self, "vr_action_history", None):
            vr_ctx["recent_actions"] = self.vr_action_history[-10:]

        if vr_ctx:
            context["vr"] = vr_ctx
        
        # Cross-modal user state summary combining vision & VR sentience
        user_state: Dict[str, Any] = {}

        vision = context.get("vision")
        if isinstance(vision, dict):
            user_state["dominant_emotion"] = vision.get("dominant_emotion")
            user_state["num_faces"] = vision.get("num_faces")
            emotions = vision.get("emotions") or {}
            if isinstance(emotions, dict) and emotions:
                try:
                    # Highest-confidence emotion
                    top_emotion, top_conf = max(
                        ((k, float(v)) for k, v in emotions.items()),
                        key=lambda kv: kv[1]
                    )
                    user_state["top_emotion_confidence"] = {top_emotion: top_conf}
                except Exception:
                    pass

        vr_metrics = getattr(self, "latest_vr_sentience_metrics", None)
        if isinstance(vr_metrics, dict) and vr_metrics:
            user_state["vr_sentience"] = vr_metrics

        vr_session = getattr(self, "vr_session_state", None)
        if isinstance(vr_session, dict) and vr_session:
            user_state["in_vr_session"] = bool(vr_session.get("active"))
            user_state["vr_environment"] = vr_session.get("environment")

        vr_status = getattr(self, "latest_vr_status", None)
        if isinstance(vr_status, dict):
            headset = vr_status.get("headset") or {}
            conn_mode = headset.get("connection_mode")
            if conn_mode:
                user_state["vr_connection_mode"] = conn_mode
            transport = headset.get("connection_transport")
            if transport:
                user_state["vr_connection_transport"] = transport

        if user_state:
            context["user_state"] = user_state
        
        return context

    async def execute_user_command(self, command: str) -> Dict[str, Any]:
        """
        Execute user commands across ALL Kingdom AI systems.
        
        SUPPORTED COMMANDS BY TAB:
        
        ## TRADING TAB
        - "buy [amount] [symbol]" - Execute buy order
        - "sell [amount] [symbol]" - Execute sell order
        - "start auto trade" - Start AI autonomous trading
        - "stop auto trade" - Stop AI autonomous trading
        - "scan arbitrage" - Scan for arbitrage opportunities
        - "analyze sentiment [symbol]" - Run sentiment analysis
        - "calculate risk" - Calculate portfolio risk
        - "scan meme coins" - Scan for meme coin opportunities
        - "generate prediction [symbol]" - Generate price prediction
        
        ## MINING TAB
        - "start mining [coin]" - Start mining a specific coin
        - "stop mining" - Stop all mining
        - "switch pool [pool_name]" - Switch mining pool
        - "optimize gpu" - Optimize GPU settings
        - "check hashrate" - Get current hashrate
        
        ## WALLET TAB
        - "check balance [chain]" - Check wallet balance
        - "send [amount] [token] to [address]" - Send tokens
        - "swap [amount] [from_token] to [to_token]" - Swap tokens
        - "bridge [amount] [token] from [chain1] to [chain2]" - Bridge tokens
        
        ## BLOCKCHAIN TAB
        - "deploy contract [type]" - Deploy smart contract
        - "call contract [address] [method]" - Call contract method
        - "monitor transactions" - Start transaction monitoring
        
        ## CODE GENERATOR TAB
        - "generate strategy [type]" - Generate trading strategy code
        - "generate bot [type]" - Generate trading bot code
        - "generate contract [type]" - Generate smart contract code
        
        ## API KEY MANAGER TAB
        - "list api keys" - List all configured API keys
        - "test api key [exchange]" - Test API key connectivity
        - "add api key [exchange]" - Add new API key (interactive)
        
        ## VR TAB
        - "start vr" - Start VR trading interface
        - "stop vr" - Stop VR interface
        
        ## SETTINGS TAB
        - "set risk level [low/medium/high]" - Set risk tolerance
        - "set max trade size [amount]" - Set maximum trade size
        
        Returns:
            Dict with "executed" bool and "response" string
        """
        cmd_lower = command.lower().strip()
        
        # =====================================================================
        # TRADING COMMANDS
        # =====================================================================
        
        # Buy command
        if cmd_lower.startswith("buy "):
            return await self._execute_trade_command(command, "buy")
        
        # Sell command
        if cmd_lower.startswith("sell "):
            return await self._execute_trade_command(command, "sell")
        
        # Start auto trade
        if "start auto" in cmd_lower and "trade" in cmd_lower:
            return await self._start_auto_trading()
        
        # Stop auto trade
        if "stop auto" in cmd_lower and "trade" in cmd_lower:
            return await self._stop_auto_trading()
        
        # Scan arbitrage
        if "scan arbitrage" in cmd_lower or "arbitrage scan" in cmd_lower:
            return await self._scan_arbitrage()
        
        # Analyze sentiment
        if "sentiment" in cmd_lower and ("analyze" in cmd_lower or "analysis" in cmd_lower):
            symbol = self._extract_symbol(command) or "BTC/USD"
            return await self._analyze_sentiment(symbol)
        
        # Calculate risk
        if "risk" in cmd_lower and ("calculate" in cmd_lower or "check" in cmd_lower):
            return await self._calculate_risk()
        
        # Scan meme coins
        if "meme" in cmd_lower and "scan" in cmd_lower:
            return await self._scan_meme_coins()
        
        # Generate prediction
        if "prediction" in cmd_lower or "predict" in cmd_lower or "forecast" in cmd_lower:
            symbol = self._extract_symbol(command) or "BTC/USD"
            return await self._generate_prediction(symbol)
        
        # =====================================================================
        # MINING COMMANDS
        # =====================================================================
        
        if "start mining" in cmd_lower:
            coin = self._extract_coin(command) or "BTC"
            return await self._start_mining(coin)
        
        if "stop mining" in cmd_lower:
            return await self._stop_mining()
        
        if "switch pool" in cmd_lower:
            pool = self._extract_pool(command)
            return await self._switch_pool(pool)
        
        if "optimize gpu" in cmd_lower:
            return await self._optimize_gpu()
        
        if "hashrate" in cmd_lower:
            return await self._check_hashrate()
        
        # =====================================================================
        # WALLET COMMANDS
        # =====================================================================
        
        if "balance" in cmd_lower and ("check" in cmd_lower or "get" in cmd_lower or "show" in cmd_lower):
            chain = self._extract_chain(command) or "ethereum"
            return await self._check_balance(chain)
        
        if cmd_lower.startswith("send "):
            return await self._send_tokens(command)
        
        if "swap" in cmd_lower:
            return await self._swap_tokens(command)
        
        if "bridge" in cmd_lower:
            return await self._bridge_tokens(command)
        
        # =====================================================================
        # BLOCKCHAIN COMMANDS
        # =====================================================================
        
        if "deploy contract" in cmd_lower:
            contract_type = self._extract_contract_type(command)
            return await self._deploy_contract(contract_type)
        
        if "call contract" in cmd_lower:
            return await self._call_contract(command)
        
        if "monitor transaction" in cmd_lower:
            return await self._monitor_transactions()
        
        # =====================================================================
        # CODE GENERATOR COMMANDS
        # =====================================================================
        
        if "generate strategy" in cmd_lower:
            strategy_type = self._extract_strategy_type(command)
            return await self._generate_strategy_code(strategy_type)
        
        if "generate bot" in cmd_lower:
            bot_type = self._extract_bot_type(command)
            return await self._generate_bot_code(bot_type)
        
        if "generate contract" in cmd_lower:
            contract_type = self._extract_contract_type(command)
            return await self._generate_contract_code(contract_type)
        
        # =====================================================================
        # API KEY COMMANDS
        # =====================================================================
        
        if "list api" in cmd_lower or "show api" in cmd_lower:
            return await self._list_api_keys()
        
        if "test api" in cmd_lower:
            exchange = self._extract_exchange(command)
            return await self._test_api_key(exchange)
        
        # =====================================================================
        # SETTINGS COMMANDS
        # =====================================================================
        
        if "set risk" in cmd_lower:
            level = self._extract_risk_level(command)
            return await self._set_risk_level(level)
        
        if "set max trade" in cmd_lower or "set trade size" in cmd_lower:
            amount = self._extract_amount(command)
            return await self._set_max_trade_size(amount)
        
        # =====================================================================
        # VR COMMANDS
        # =====================================================================
        
        if "start vr" in cmd_lower:
            return await self._start_vr()
        
        if "stop vr" in cmd_lower:
            return await self._stop_vr()
        
        # Not a recognized command
        return {"executed": False, "response": None}

    # =========================================================================
    # TRADING COMMAND IMPLEMENTATIONS
    # =========================================================================
    
    async def _execute_trade_command(self, command: str, side: str) -> Dict[str, Any]:
        """Execute a buy or sell trade command."""
        try:
            parts = command.lower().split()
            amount = 0.0
            symbol = "BTC/USD"
            
            for i, part in enumerate(parts):
                try:
                    amount = float(part)
                except ValueError:
                    if "/" in part.upper() or part.upper() in ["BTC", "ETH", "SOL", "XRP", "DOGE"]:
                        symbol = part.upper()
                        if "/" not in symbol:
                            symbol = f"{symbol}/USD"
            
            if amount <= 0:
                amount = 0.01  # Default small amount
            
            # Execute via RealExchangeExecutor
            if self.real_exchange_executor:
                result = await self.real_exchange_executor.execute_order(
                    symbol=symbol,
                    side=side,
                    amount=amount,
                    order_type="market"
                )
                return {
                    "executed": True,
                    "response": f"✅ {side.upper()} order executed: {amount} {symbol}\nResult: {result}"
                }
            else:
                # Publish event for GUI to handle
                if self.event_bus:
                    self.event_bus.publish("trading.execute_order", {
                        "symbol": symbol,
                        "side": side,
                        "amount": amount,
                        "type": "market"
                    })
                return {
                    "executed": True,
                    "response": f"📤 {side.upper()} order request sent: {amount} {symbol}"
                }
        except Exception as e:
            return {"executed": True, "response": f"❌ Trade error: {e}"}

    async def _start_auto_trading(self) -> Dict[str, Any]:
        """Start AI autonomous trading."""
        try:
            self.enable_autonomous_mode(self.max_trade_size_usd, self.risk_tolerance)
            
            # Trigger the analyze and start flow
            if self.event_bus:
                self.event_bus.publish("ai.autotrade.analyze_and_start", {
                    "max_trade_size_usd": self.max_trade_size_usd,
                    "risk_tolerance": self.risk_tolerance
                })
            
            return {
                "executed": True,
                "response": f"🤖 AUTO TRADE STARTED\n"
                           f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                           f"Max Trade Size: ${self.max_trade_size_usd}\n"
                           f"Risk Tolerance: {self.risk_tolerance}\n"
                           f"Crypto: ENABLED\n"
                           f"Stocks: ENABLED\n"
                           f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                           f"Thoth AI is now trading autonomously!"
            }
        except Exception as e:
            return {"executed": True, "response": f"❌ Auto trade start error: {e}"}

    async def _stop_auto_trading(self) -> Dict[str, Any]:
        """Stop AI autonomous trading."""
        try:
            self.disable_autonomous_mode()
            self.crypto_autonomous = False
            self.stocks_autonomous = False
            
            if self.event_bus:
                self.event_bus.publish("ai.autotrade.crypto.disable", {})
                self.event_bus.publish("ai.autotrade.stocks.disable", {})
            
            return {
                "executed": True,
                "response": "🛑 AUTO TRADE STOPPED\nAll autonomous trading has been disabled."
            }
        except Exception as e:
            return {"executed": True, "response": f"❌ Auto trade stop error: {e}"}

    async def _scan_arbitrage(self) -> Dict[str, Any]:
        """Scan for arbitrage opportunities."""
        try:
            if self.live_arbitrage:
                opportunities = await self.live_arbitrage.scan()
                if opportunities:
                    lines = ["💰 ARBITRAGE OPPORTUNITIES FOUND", "━" * 40]
                    for opp in opportunities[:5]:
                        lines.append(f"{opp.get('symbol')}: {opp.get('spread_pct', 0):.2f}% spread")
                    return {"executed": True, "response": "\n".join(lines)}
            
            if self.event_bus:
                self.event_bus.publish("trading.arbitrage.scan", {})
            
            return {"executed": True, "response": "🔍 Arbitrage scan initiated. Results will appear in the Trading Tab."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Arbitrage scan error: {e}"}

    async def _analyze_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Analyze market sentiment for a symbol."""
        try:
            if self.live_sentiment:
                result = await self.live_sentiment.analyze(symbol)
                score = result.get("score", 0)
                sentiment = "BULLISH" if score > 0 else "BEARISH" if score < 0 else "NEUTRAL"
                return {
                    "executed": True,
                    "response": f"🎭 SENTIMENT ANALYSIS: {symbol}\n"
                               f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                               f"Sentiment: {sentiment} ({score:+.2f})\n"
                               f"Confidence: {result.get('confidence', 0):.1f}%"
                }
            
            if self.event_bus:
                self.event_bus.publish("trading.sentiment.analyze", {"symbol": symbol})
            
            return {"executed": True, "response": f"🔍 Sentiment analysis for {symbol} initiated."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Sentiment analysis error: {e}"}

    async def _calculate_risk(self) -> Dict[str, Any]:
        """Calculate portfolio risk."""
        try:
            if self.live_risk_manager:
                metrics = await self.live_risk_manager.calculate()
                return {
                    "executed": True,
                    "response": f"🛡️ RISK ANALYSIS\n"
                               f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                               f"Total Exposure: ${metrics.get('total_exposure', 0):,.2f}\n"
                               f"Max Drawdown: {metrics.get('max_drawdown', 0):.1f}%\n"
                               f"VaR (95%): ${metrics.get('var_95', 0):,.2f}\n"
                               f"Sharpe Ratio: {metrics.get('sharpe', 0):.2f}"
                }
            
            if self.event_bus:
                self.event_bus.publish("trading.risk.calculate", {})
            
            return {"executed": True, "response": "📊 Risk calculation initiated."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Risk calculation error: {e}"}

    async def _scan_meme_coins(self) -> Dict[str, Any]:
        """Scan for meme coin opportunities."""
        try:
            if self.live_meme_scanner:
                results = await self.live_meme_scanner.scan()
                if results:
                    lines = ["🚀 MEME COIN SCAN RESULTS", "━" * 40]
                    for coin in results[:5]:
                        emoji = "🟢" if coin.get("change", 0) > 0 else "🔴"
                        lines.append(f"{emoji} {coin.get('symbol')}: {coin.get('change', 0):+.1f}%")
                    return {"executed": True, "response": "\n".join(lines)}
            
            if self.event_bus:
                self.event_bus.publish("meme_coin.scan", {})
            
            return {"executed": True, "response": "🔍 Meme coin scan initiated."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Meme scan error: {e}"}

    async def _generate_prediction(self, symbol: str) -> Dict[str, Any]:
        """Generate price prediction for a symbol."""
        try:
            if self.event_bus:
                self.event_bus.publish("timeseries.predict", {"symbol": symbol})
            
            return {"executed": True, "response": f"🔮 Price prediction for {symbol} initiated. Results will appear in Trading Tab."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Prediction error: {e}"}

    # =========================================================================
    # MINING COMMAND IMPLEMENTATIONS
    # =========================================================================
    
    async def _start_mining(self, coin: str) -> Dict[str, Any]:
        """Start mining a specific coin."""
        try:
            if self.event_bus:
                self.event_bus.publish("mining.start", {"coin": coin})
            return {"executed": True, "response": f"⛏️ Mining {coin} started!"}
        except Exception as e:
            return {"executed": True, "response": f"❌ Mining start error: {e}"}

    async def _stop_mining(self) -> Dict[str, Any]:
        """Stop all mining operations."""
        try:
            if self.event_bus:
                self.event_bus.publish("mining.stop", {})
            return {"executed": True, "response": "🛑 Mining stopped."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Mining stop error: {e}"}

    async def _switch_pool(self, pool: str) -> Dict[str, Any]:
        """Switch mining pool."""
        try:
            if self.event_bus:
                self.event_bus.publish("mining.switch_pool", {"pool": pool})
            return {"executed": True, "response": f"🔄 Switched to pool: {pool}"}
        except Exception as e:
            return {"executed": True, "response": f"❌ Pool switch error: {e}"}

    async def _optimize_gpu(self) -> Dict[str, Any]:
        """Optimize GPU settings for mining."""
        try:
            if self.event_bus:
                self.event_bus.publish("mining.optimize_gpu", {})
            return {"executed": True, "response": "⚡ GPU optimization started."}
        except Exception as e:
            return {"executed": True, "response": f"❌ GPU optimization error: {e}"}

    async def _check_hashrate(self) -> Dict[str, Any]:
        """Check current mining hashrate."""
        try:
            if self.event_bus:
                self.event_bus.publish("mining.get_hashrate", {})
            return {"executed": True, "response": "📊 Hashrate check initiated. Results will appear in Mining Tab."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Hashrate check error: {e}"}

    # =========================================================================
    # WALLET COMMAND IMPLEMENTATIONS
    # =========================================================================
    
    async def _check_balance(self, chain: str) -> Dict[str, Any]:
        """Check wallet balance on a specific chain."""
        try:
            if self.event_bus:
                self.event_bus.publish("wallet.get_balance", {"chain": chain})
            return {"executed": True, "response": f"💰 Checking {chain} balance..."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Balance check error: {e}"}

    async def _send_tokens(self, command: str) -> Dict[str, Any]:
        """Send tokens to an address."""
        try:
            # Parse: send [amount] [token] to [address]
            if self.event_bus:
                self.event_bus.publish("wallet.send", {"command": command})
            return {"executed": True, "response": "📤 Send transaction initiated. Please confirm in Wallet Tab."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Send error: {e}"}

    async def _swap_tokens(self, command: str) -> Dict[str, Any]:
        """Swap tokens."""
        try:
            if self.event_bus:
                self.event_bus.publish("wallet.swap", {"command": command})
            return {"executed": True, "response": "🔄 Swap initiated. Please confirm in Wallet Tab."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Swap error: {e}"}

    async def _bridge_tokens(self, command: str) -> Dict[str, Any]:
        """Bridge tokens between chains."""
        try:
            if self.event_bus:
                self.event_bus.publish("wallet.bridge", {"command": command})
            return {"executed": True, "response": "🌉 Bridge transaction initiated. Please confirm in Wallet Tab."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Bridge error: {e}"}

    # =========================================================================
    # BLOCKCHAIN COMMAND IMPLEMENTATIONS
    # =========================================================================
    
    async def _deploy_contract(self, contract_type: str) -> Dict[str, Any]:
        """Deploy a smart contract."""
        try:
            if self.event_bus:
                self.event_bus.publish("blockchain.deploy_contract", {"type": contract_type})
            return {"executed": True, "response": f"📜 Deploying {contract_type} contract..."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Deploy error: {e}"}

    async def _call_contract(self, command: str) -> Dict[str, Any]:
        """Call a smart contract method."""
        try:
            if self.event_bus:
                self.event_bus.publish("blockchain.call_contract", {"command": command})
            return {"executed": True, "response": "📞 Contract call initiated."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Contract call error: {e}"}

    async def _monitor_transactions(self) -> Dict[str, Any]:
        """Start transaction monitoring."""
        try:
            if self.event_bus:
                self.event_bus.publish("blockchain.monitor_start", {})
            return {"executed": True, "response": "👁️ Transaction monitoring started."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Monitor error: {e}"}

    # =========================================================================
    # CODE GENERATOR COMMAND IMPLEMENTATIONS
    # =========================================================================
    
    async def _generate_strategy_code(self, strategy_type: str) -> Dict[str, Any]:
        """Generate trading strategy code."""
        try:
            if self.event_bus:
                self.event_bus.publish("codegen.generate_strategy", {"type": strategy_type})
            return {"executed": True, "response": f"💻 Generating {strategy_type} strategy code..."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Code generation error: {e}"}

    async def _generate_bot_code(self, bot_type: str) -> Dict[str, Any]:
        """Generate trading bot code."""
        try:
            if self.event_bus:
                self.event_bus.publish("codegen.generate_bot", {"type": bot_type})
            return {"executed": True, "response": f"🤖 Generating {bot_type} bot code..."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Bot generation error: {e}"}

    async def _generate_contract_code(self, contract_type: str) -> Dict[str, Any]:
        """Generate smart contract code."""
        try:
            if self.event_bus:
                self.event_bus.publish("codegen.generate_contract", {"type": contract_type})
            return {"executed": True, "response": f"📜 Generating {contract_type} contract code..."}
        except Exception as e:
            return {"executed": True, "response": f"❌ Contract generation error: {e}"}

    # =========================================================================
    # API KEY COMMAND IMPLEMENTATIONS
    # =========================================================================
    
    async def _list_api_keys(self) -> Dict[str, Any]:
        """List all configured API keys."""
        try:
            if self.api_keys:
                lines = ["🔑 CONFIGURED API KEYS", "━" * 40]
                for key_name in list(self.api_keys.keys())[:20]:
                    masked = "***" + key_name[-4:] if len(key_name) > 4 else "****"
                    lines.append(f"• {key_name}: {masked}")
                return {"executed": True, "response": "\n".join(lines)}
            return {"executed": True, "response": "No API keys configured."}
        except Exception as e:
            return {"executed": True, "response": f"❌ API key list error: {e}"}

    async def _test_api_key(self, exchange: str) -> Dict[str, Any]:
        """Test API key connectivity for an exchange."""
        try:
            if self.event_bus:
                self.event_bus.publish("api_key.test", {"exchange": exchange})
            return {"executed": True, "response": f"🔍 Testing {exchange} API key..."}
        except Exception as e:
            return {"executed": True, "response": f"❌ API key test error: {e}"}

    # =========================================================================
    # SETTINGS COMMAND IMPLEMENTATIONS
    # =========================================================================
    
    async def _set_risk_level(self, level: str) -> Dict[str, Any]:
        """Set risk tolerance level."""
        try:
            self.risk_tolerance = level
            if self.event_bus:
                self.event_bus.publish("settings.risk_level", {"level": level})
            return {"executed": True, "response": f"⚙️ Risk level set to: {level}"}
        except Exception as e:
            return {"executed": True, "response": f"❌ Settings error: {e}"}

    async def _set_max_trade_size(self, amount: float) -> Dict[str, Any]:
        """Set maximum trade size."""
        try:
            self.max_trade_size_usd = amount
            if self.event_bus:
                self.event_bus.publish("settings.max_trade_size", {"amount": amount})
            return {"executed": True, "response": f"⚙️ Max trade size set to: ${amount}"}
        except Exception as e:
            return {"executed": True, "response": f"❌ Settings error: {e}"}

    # =========================================================================
    # VR COMMAND IMPLEMENTATIONS
    # =========================================================================
    
    async def _start_vr(self) -> Dict[str, Any]:
        """Start VR trading interface."""
        try:
            if self.event_bus:
                self.event_bus.publish("vr.start", {})
            return {"executed": True, "response": "🥽 VR trading interface starting..."}
        except Exception as e:
            return {"executed": True, "response": f"❌ VR start error: {e}"}

    async def _stop_vr(self) -> Dict[str, Any]:
        """Stop VR trading interface."""
        try:
            if self.event_bus:
                self.event_bus.publish("vr.stop", {})
            return {"executed": True, "response": "🛑 VR interface stopped."}
        except Exception as e:
            return {"executed": True, "response": f"❌ VR stop error: {e}"}

    # =========================================================================
    # HELPER METHODS FOR COMMAND PARSING
    # =========================================================================
    
    def _extract_symbol(self, command: str) -> Optional[str]:
        """Extract trading symbol from command."""
        symbols = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "DOT", "LINK", "AAPL", "MSFT", "GOOGL", "TSLA"]
        for sym in symbols:
            if sym.lower() in command.lower():
                return f"{sym}/USD"
        return None

    def _extract_coin(self, command: str) -> Optional[str]:
        """Extract coin name from command."""
        coins = ["BTC", "ETH", "LTC", "XMR", "RVN", "ERGO", "KAS", "FLUX"]
        for coin in coins:
            if coin.lower() in command.lower():
                return coin
        return None

    def _extract_pool(self, command: str) -> str:
        """Extract pool name from command."""
        pools = ["2miners", "f2pool", "ethermine", "flexpool", "hiveon", "nanopool"]
        for pool in pools:
            if pool.lower() in command.lower():
                return pool
        return "default"

    def _extract_chain(self, command: str) -> str:
        """Extract blockchain name from command."""
        chains = ["ethereum", "bitcoin", "polygon", "bsc", "arbitrum", "optimism", "base", "avalanche", "solana"]
        for chain in chains:
            if chain.lower() in command.lower():
                return chain
        return "ethereum"

    def _extract_contract_type(self, command: str) -> str:
        """Extract contract type from command."""
        types = ["erc20", "erc721", "erc1155", "defi", "staking", "governance", "multisig"]
        for t in types:
            if t.lower() in command.lower():
                return t
        return "erc20"

    def _extract_strategy_type(self, command: str) -> str:
        """Extract strategy type from command."""
        types = ["momentum", "mean_reversion", "arbitrage", "grid", "dca", "breakout", "scalping"]
        for t in types:
            if t.lower() in command.lower():
                return t
        return "momentum"

    def _extract_bot_type(self, command: str) -> str:
        """Extract bot type from command."""
        types = ["trading", "sniper", "arbitrage", "market_maker", "copy_trade"]
        for t in types:
            if t.lower() in command.lower():
                return t
        return "trading"

    def _extract_exchange(self, command: str) -> str:
        """Extract exchange name from command."""
        exchanges = ["kraken", "binance", "bitstamp", "htx", "coinbase", "alpaca", "oanda"]
        for ex in exchanges:
            if ex.lower() in command.lower():
                return ex
        return "kraken"

    def _extract_risk_level(self, command: str) -> str:
        """Extract risk level from command."""
        if "high" in command.lower() or "aggressive" in command.lower():
            return "high"
        elif "low" in command.lower() or "conservative" in command.lower():
            return "low"
        return "medium"

    def _extract_amount(self, command: str) -> float:
        """Extract numeric amount from command."""
        import re
        matches = re.findall(r'[\d,]+\.?\d*', command)
        for match in matches:
            try:
                return float(match.replace(',', ''))
            except ValueError:
                continue
        return 1000.0
