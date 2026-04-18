#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Mining Intelligence Module

This module provides advanced AI-driven mining optimization capabilities,
connecting the mining system with ThothAI and multi-model brain systems
to maximize mining performance, efficiency, and profitability.

Features:
- AI-driven mining algorithm selection
- Dynamic hashrate optimization
- Profitability analysis and forecasting
- Multi-algorithm support and switching
- Hardware efficiency optimization
- Market trend analysis for optimal coin selection
- Self-improving strategies using ThothAI
- Quantum-inspired optimization algorithms
- Airdrop discovery and farming automation
- Competitive mining intelligence
- Automated profit-taking and reinvestment
- Intelligent portfolio management
- Adaptive trading strategies for underperforming assets
"""

# Standard library imports
import asyncio
import logging
import random
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

# Third party imports

# Core Kingdom AI imports
from core.base_component import BaseComponent

# Configure logging
logger = logging.getLogger("KingdomAI.MiningIntelligence")


# Define enums and data classes for type safety
class MiningAlgorithm(Enum):
    """Supported mining algorithms"""
    SHA256 = "sha256"           # Bitcoin
    ETHASH = "ethash"           # Ethereum
    SCRYPT = "scrypt"           # Litecoin
    EQUIHASH = "equihash"       # Zcash
    RANDOMX = "randomx"         # Monero
    KADENA = "kadena"           # Kadena
    KASPA = "kaspa"             # Kaspa
    ERGO = "autolykos2"         # Ergo
    BLAKE3 = "blake3"           # Alephium
    QUANTUM = "quantum"         # Quantum-enabled mining


@dataclass
class CoinTarget:
    """Coin mining target with tracking"""
    symbol: str
    name: str
    algorithm: MiningAlgorithm
    target_amount: float = 1000.0  # Target to mine 1000 coins
    current_amount: float = 0.0
    priority: float = 1.0  # Priority multiplier
    daily_emission: float = 0.0  # Estimated daily emission
    last_mined: Optional[datetime] = None
    urgency_score: float = 0.0  # Calculated urgency for mining
    profitability_score: float = 0.0  # Current mining profitability


@dataclass
class AirdropOpportunity:
    """Represents an airdrop opportunity to farm"""
    id: str
    project: str
    chain: str
    estimated_value: float
    requirements: List[str]
    deadline: Optional[datetime]
    url: str
    status: str = "discovered"  # discovered, in_progress, completed, failed
    confidence: float = 0.0
    completion_percentage: float = 0.0
    eligibility_checked: bool = False  # Whether eligibility has been verified
    wallets_used: List[str] = field(default_factory=list)  # Wallets used for this airdrop


@dataclass
class MiningStats:
    """Mining statistics for optimization"""
    algorithm: str
    hashrate: float
    power_usage: float
    coins_per_day: float
    value_per_day: float
    efficiency: float  # value per watt
    timestamp: datetime
    competition_level: float = 0.0  # Level of mining competition (0-10)
    network_difficulty_trend: float = 0.0  # Trend in network difficulty (-1 to 1)


class MarketSignal(Enum):
    """Market signals for trading decisions"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class TradingSignal:
    """Trading signal for a specific coin"""
    symbol: str
    signal: MarketSignal
    confidence: float  # 0.0 to 1.0
    timestamp: datetime
    source: str  # e.g., "thoth_ai", "technical_analysis", "fundamental_analysis"
    reasons: List[str] = field(default_factory=list)

class MiningIntelligence(BaseComponent):
    """Advanced AI-driven mining intelligence for optimizing cryptocurrency mining operations.
    
    This component integrates with the Mining System and ThothAI to provide intelligent
    mining recommendations, dynamic algorithm switching, profitability analysis,
    hardware optimization, and airdrop farming capabilities.
    
    Features:
    - Aggressive 24/7 mining to reach 1000+ coins per cryptocurrency
    - AI-driven algorithm selection and hardware optimization
    - Quantum-inspired optimization techniques for mining efficiency
    - Competitive analysis to exploit mining opportunities
    - Automated airdrop discovery and farming
    - Dynamic trading of underperforming assets
    - Intelligent portfolio management with advanced risk assessment
    - Market trend analysis for optimal entry and exit points
    - Competitive learning from other miners' strategies
    - Automated profit taking and reinvestment
    """
    
    def __init__(self, name="MiningIntelligence", event_bus=None, config=None, redis_nexus=None, api_key_manager=None):
        """
        Initialize the Mining Intelligence component.
        
        Args:
            name: Component name
            event_bus: Event bus for inter-component communication
            config: Configuration dictionary
            redis_nexus: Redis connection for caching and persistence
            api_key_manager: API key manager for handling API keys
        """
        super().__init__(name=name, event_bus=event_bus, config=config)
        
        # References to other components
        self.event_bus = event_bus
        self.config = config or {}
        self.redis_nexus = redis_nexus
        self.api_key_manager = api_key_manager
        self.thoth_ai = None
        self.trading_intelligence = None
        self.blockchain_connector = None
        self.wallet_manager = None
        self.market_data_provider = None
        self.core_mining_system = None
        self.mining_dashboard = None
        
        # Data structures for tracking mining information
        self.coin_data = {}            # Store coin market and mining data
        self.target_coins = []         # List of coins we are targeting to mine
        self.airdrop_opportunities = [] # List of discovered airdrop opportunities
        self.mining_rewards_by_coin = {} # Track mining rewards by coin
        self.mining_stats = {}         # Statistics about mining performance
        
        # Configuration settings (with defaults)
        self.aggressive_mining = True
        self.auto_adjust_mining = True
        self.parallel_mining_active = False
        self.auto_farm_airdrops = False
        self.auto_collect_rewards = True
        
        # AI model instances
        self.difficulty_prediction_model = None
        self.profitability_model = None
        self.hardware_optimizer = None
        
        # Background tasks
        self.optimization_task = None
        self.airdrop_scanning_task = None
        self.portfolio_management_task = None
        self.ai_mining_focus_task = None
        
        self.ai_mining_focus_interval = 30
        self._trading_system_readiness: Dict[str, Any] = {"state": "UNKNOWN", "auto_trade_started": False}
    
    @property
    def component_name(self):
        """Return the component name for use with the event bus."""
        return "MiningIntelligence"
        
    async def initialize(self, event_bus=None) -> bool:
        """
        Initialize the Mining Intelligence component and connect to the event bus.
        
        This method is called by the ComponentManager during system startup.
        It establishes connections to other components, sets up event subscriptions,
        and prepares the component for operation.
        
        Args:
            event_bus: The event bus for inter-component communication
            
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            self.logger.info("Initializing Mining Intelligence component")
            
            # Set event bus if provided
            if event_bus:
                self.event_bus = event_bus
            
            # Check if event bus is available
            if not self.event_bus:
                self.logger.error("No event bus available for initialization")
                return False
            
            # Load configuration settings
            if not await self._load_config():
                self.logger.error("Failed to load configuration")
                return False
            
            # Connect to other required components
            if not await self._connect_to_components():
                self.logger.error("Failed to connect to other components")
                return False
            
            # Set up event subscriptions
            if not await self._setup_event_subscriptions():
                self.logger.error("Failed to set up event subscriptions")
                return False
            
            # Initialize AI models and optimization systems
            if not await self._initialize_ai_models():
                self.logger.error("Failed to initialize AI models")
                return False
            
            # Start background tasks
            if not await self._start_background_tasks():
                self.logger.error("Failed to start background tasks")
                return False
            
            self._initialized = True
            self.logger.info("Mining Intelligence component initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing Mining Intelligence component: {e}")
            self.logger.error(traceback.format_exc())
            return False
        
    async def _load_config(self):
        """
        Load configuration settings for the Mining Intelligence component.
        
        Reads configuration from the config object or environment variables,
        initializing default values where necessary.
        
        Returns:
            bool: True if configuration was loaded successfully, False otherwise
        """
        try:
            self.logger.info("Loading Mining Intelligence configuration")
            
            # Set intervals from config or use defaults
            self.optimization_interval = self.config.get("optimization_interval", 300)  # 5 minutes
            self.airdrop_scanning_interval = self.config.get("airdrop_scanning_interval", 600)  # 10 minutes
            self.portfolio_update_interval = self.config.get("portfolio_update_interval", 1800)  # 30 minutes
            
            # Set operational flags from config
            self.aggressive_mining = self.config.get("aggressive_mining", True)
            self.auto_adjust_mining = self.config.get("auto_adjust_mining", True)
            self.parallel_mining_active = self.config.get("parallel_mining_active", False)
            self.auto_farm_airdrops = self.config.get("auto_farm_airdrops", False)
            self.auto_collect_rewards = self.config.get("auto_collect_rewards", True)
            self.auto_trade_underperforming = self.config.get("auto_trade_underperforming", False)
            
            # Load algorithm weights for profitability calculations
            weight_config = self.config.get("algorithm_weights", {})
            self.algorithm_weights = {
                "price": weight_config.get("price", 0.3),
                "volume": weight_config.get("volume", 0.1),
                "difficulty": weight_config.get("difficulty", 0.3),
                "difficulty_trend": weight_config.get("difficulty_trend", 0.2),
                "market_cap": weight_config.get("market_cap", 0.1)
            }
            
            self.logger.info("Configuration loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _calculate_initial_profitability(self, coin_data):
        """
        Calculate initial profitability score for a new coin using multiple market factors.
        
        This method uses a weighted combination of network hashrate, token price,
        market sentiment, mining difficulty trend, and emission rate to calculate
        a comprehensive profitability score for mining a specific cryptocurrency.
        
        Args:
            coin_data (dict): Data about the coin including price, hashrate, difficulty, etc.
            
        Returns:
            float: Initial profitability score (0.0 to 1.0) where higher is more profitable
        """
        self.logger.debug(f"Calculating profitability for {coin_data.get('symbol', 'unknown coin')}")
        
        # Default score if we can't calculate properly
        default_score = 0.3
        
        try:
            # Extract key metrics from coin data
            symbol = coin_data.get('symbol', '').upper()
            price = coin_data.get('price', 0.0)
            market_cap = coin_data.get('market_cap', 0.0)
            hashrate = coin_data.get('network_hashrate', 0.0)
            difficulty = coin_data.get('difficulty', 0.0)
            algorithm = coin_data.get('algorithm', '')
            daily_volume = coin_data.get('volume_24h', 0.0)
            block_reward = coin_data.get('block_reward', 0.0)
            blocks_per_day = coin_data.get('blocks_per_day', 0.0)
            sentiment_score = coin_data.get('sentiment_score', 0.5)  # Default neutral
            difficulty_trend = coin_data.get('difficulty_trend', 0.0)  # -1.0 to 1.0
            
            # Basic validation
            if price <= 0 or difficulty <= 0 or hashrate <= 0:
                self.logger.warning(f"Missing critical data for {symbol}, using default score")
                return default_score
            if price <= 0 or difficulty <= 0 or block_reward <= 0:
                return 0.0
                
            # Calculate profitability score using multiple factors
            base_score = (price * block_reward) / max(1.0, difficulty)
            volume_factor = min(1.0, volume / 1000000) * 0.2
            market_cap_factor = min(1.0, market_cap / 100000000) * 0.1
            
            # Combined score
            profitability_score = base_score * (1 + volume_factor + market_cap_factor) * 100
            
            return max(0.0, min(100.0, profitability_score))  # Clamp between 0 and 100
            
        except Exception as e:
            self.logger.error(f"Error calculating initial profitability: {e}")
            return 0.0
            
    async def _connect_to_components(self):
        """
        Connect to other required components via the event bus.
        
        This method establishes connections to dependent components such as
        ThothAI, Trading Intelligence, and the Blockchain Connector.
        
        Returns:
            bool: True if connections were established successfully, False otherwise
        """
        try:
            self.logger.info("Connecting to other components")
            
            # Skip if no event bus is available
            if not self.event_bus:
                self.logger.error("No event bus available for component connections")
                return False
                
            # Get references to other components from the event bus
            components = await self.event_bus.get_registered_components()
            
            # Connect to each required component
            for component_name in components:
                if component_name == "ThothAI":
                    self.thoth_ai = components[component_name]
                    self.logger.debug("Connected to ThothAI component")
                    
                elif component_name == "TradingIntelligence":
                    self.trading_intelligence = components[component_name]
                    self.logger.debug("Connected to Trading Intelligence component")
                    
                elif component_name == "BlockchainConnector":
                    self.blockchain_connector = components[component_name]
                    self.logger.debug("Connected to Blockchain Connector component")
                    
                elif component_name == "WalletManager":
                    self.wallet_manager = components[component_name]
                    self.logger.debug("Connected to Wallet Manager component")
                    
                elif component_name == "MarketDataProvider":
                    self.market_data_provider = components[component_name]
                    self.logger.debug("Connected to Market Data Provider component")
                    
                elif component_name == "CoreMiningSystem":
                    self.core_mining_system = components[component_name]
                    self.logger.debug("Connected to Core Mining System component")
                    
                elif component_name == "MiningDashboard":
                    self.mining_dashboard = components[component_name]
                    self.logger.debug("Connected to Mining Dashboard component")
            
            # Verify essential components
            missing_components = []
            if not self.core_mining_system:
                missing_components.append("CoreMiningSystem")
            if not self.market_data_provider:
                missing_components.append("MarketDataProvider")
            
            if missing_components:
                self.logger.warning(f"Missing essential components: {', '.join(missing_components)}")
                # We'll continue even with missing components, but log a warning
            
            self.logger.info("Component connections established successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to components: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _setup_event_subscriptions(self):
        """
        Set up event subscriptions for the Mining Intelligence component.
        
        This method subscribes to relevant events on the event bus that
        the Mining Intelligence component needs to respond to.
        
        Returns:
            bool: True if subscriptions were set up successfully, False otherwise
        """
        try:
            self.logger.info("Setting up event subscriptions")
            
            # Skip if no event bus is available
            if not self.event_bus:
                self.logger.error("No event bus available for event subscriptions")
                return False
                
            # Subscribe to mining-related events
            await self.event_bus.subscribe("mining.difficulty_update", self._handle_difficulty_update)
            await self.event_bus.subscribe("mining.reward_update", self._handle_reward_update)
            await self.event_bus.subscribe("mining.algorithm_performance", self._handle_algorithm_performance)
            
            # Subscribe to market-related events
            await self.event_bus.subscribe("market.price_update", self._handle_price_update)
            await self.event_bus.subscribe("market.trend_update", self._handle_trend_update)
            
            # Subscribe to airdrop-related events
            await self.event_bus.subscribe("airdrop.discovery", self._handle_airdrop_opportunity)
            await self.event_bus.subscribe("airdrop.eligibility_result", self._handle_airdrop_eligibility)
            await self.event_bus.subscribe("airdrop.register.requested", self._handle_airdrop_register_requested)
            await self.event_bus.subscribe("airdrop.scan.request", self._handle_airdrop_scan_request)
            
            # Subscribe to system control events
            await self.event_bus.subscribe("system.status_request", self._handle_status_request)
            await self.event_bus.subscribe("trading.system.readiness", self._handle_trading_system_readiness)
            
            # KAIG Intelligence Bridge — receive mining directives & speed mandates
            await self.event_bus.subscribe("kaig.intel.mining.directive", self._handle_kaig_mining_directive)
            await self.event_bus.subscribe("kaig.intel.speed.mandate", self._handle_kaig_speed_mandate)
            # Also subscribe to trading directive for full 3-target awareness + rebrand resilience
            await self.event_bus.subscribe("kaig.intel.trading.directive", self._handle_kaig_trading_directive)
            await self.event_bus.subscribe("kaig.ath.update", self._handle_kaig_ath_update)
            await self.event_bus.subscribe("kaig.identity.changed", self._handle_identity_changed)
            
            self.logger.info("Event subscriptions set up successfully (incl. KAIG directives)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up event subscriptions: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def _initialize_ai_models(self):
        """
        Initialize AI models for mining optimization.
        
        This method sets up AI models for difficulty prediction,
        profitability analysis, and hardware optimization.
        
        Returns:
            bool: True if models were initialized successfully, False otherwise
        """
        try:
            self.logger.info("Initializing AI models")
            
            # Check if ThothAI is available for model initialization
            if not self.thoth_ai:
                # SOTA 2026 FIX: ThothAI is optional - use debug not warning
                self.logger.debug("ℹ️ ThothAI not available for model initialization (using basic models)")
                # Continue with basic models instead
            
            # Initialize the models
            self.difficulty_prediction_model = {
                "type": "simple_regression",
                "version": "0.1",
                "last_updated": datetime.now().isoformat()
            }
            
            self.profitability_model = {
                "type": "multi_factor",
                "version": "0.1",
                "factors": self.algorithm_weights,
                "last_updated": datetime.now().isoformat()
            }
            
            self.hardware_optimizer = {
                "type": "efficiency_optimizer",
                "version": "0.1",
                "last_updated": datetime.now().isoformat()
            }
            
            self.logger.info("AI models initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing AI models: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def _start_background_tasks(self):
        """
        Start background tasks for ongoing mining intelligence operations.
        
        This method starts tasks for optimization, airdrop scanning, and
        portfolio management that run periodically in the background.
        
        Returns:
            bool: True if tasks were started successfully, False otherwise
        """
        try:
            self.logger.info("Starting background tasks")
            
            # Start optimization loop
            self.optimization_task = asyncio.create_task(
                self._optimization_loop()
            )
            
            self.ai_mining_focus_task = asyncio.create_task(
                self._ai_mining_focus_loop()
            )
            
            # Start airdrop scanning loop if enabled
            if self.auto_farm_airdrops:
                self.airdrop_scanning_task = asyncio.create_task(
                    self._airdrop_scanning_loop()
                )
            
            # Start portfolio management loop
            self.portfolio_management_task = asyncio.create_task(
                self._portfolio_management_loop()
            )
            
            self.logger.info("Background tasks started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting background tasks: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    # ── KAIG INTELLIGENCE BRIDGE HANDLERS ────────────────────────

    async def _handle_kaig_mining_directive(self, event_data):
        """Receive KAIG mining directive — mission, reward routing, algorithm priorities.

        This is the bridge between KAIG tokenomics goals and this mining engine.
        Every cycle the bridge publishes what we should mine and how fast.
        """
        try:
            if not isinstance(event_data, dict):
                return
            if not hasattr(self, '_kaig_directive'):
                self._kaig_directive = {}
            self._kaig_directive = event_data

            # Apply aggressive mode from directive
            aggressive = event_data.get("aggressive_mode", True)
            if aggressive and not self.aggressive_mining:
                self.aggressive_mining = True
                self.logger.info("KAIG directive: aggressive mining ENABLED")

            # Apply speed mandate — tighten optimization interval
            opt_interval = event_data.get("optimization_interval_seconds", 60)
            if hasattr(self, 'optimization_interval'):
                self.optimization_interval = min(self.optimization_interval, max(30, opt_interval))

            cycle = event_data.get("cycle", 0)
            if cycle <= 1 or cycle % 10 == 0:
                self.logger.info(
                    "KAIG Mining Directive received: aggressive=%s, "
                    "target_coins=%d, auto_switch=%s, mining_today=$%.2f",
                    event_data.get("aggressive_mode", "?"),
                    event_data.get("target_coins_mined", 0),
                    event_data.get("auto_switch_algorithm", "?"),
                    event_data.get("mining_rewards_today_usd", 0),
                )
        except Exception as e:
            self.logger.error(f"Error handling KAIG mining directive: {e}")

    async def _handle_kaig_speed_mandate(self, event_data):
        """Receive global speed mandate from KAIG bridge — all systems must prioritize speed."""
        try:
            if not isinstance(event_data, dict):
                return
            mining_interval = event_data.get("mining_optimization_interval", 60)
            if hasattr(self, 'optimization_interval'):
                self.optimization_interval = min(self.optimization_interval, max(30, mining_interval))
            self.logger.debug("KAIG speed mandate received: mining_interval=%ds", mining_interval)
        except Exception as e:
            self.logger.debug(f"Error handling KAIG speed mandate: {e}")

    async def _handle_kaig_trading_directive(self, event_data):
        """Receive KAIG trading directive — carries ALL 3 targets.

        Mining must know:
        1. SURVIVAL FLOOR: $26K realized → $13K treasury (existential)
        2. KAIG PRICE FLOOR: 1 KAIG > highest crypto ATH ever (live-monitored)
        3. ULTIMATE TARGET: $2T (aspirational, always pursue)
        All mining rewards fund KAIG buybacks via the 50% profit route.
        """
        try:
            if not isinstance(event_data, dict):
                return
            self._kaig_trading_directive = event_data
            floor = event_data.get("kaig_survival_floor", {})
            pf = event_data.get("kaig_price_floor", {})
            survival_met = floor.get("survival_met", False)
            if not survival_met and not self.aggressive_mining:
                self.aggressive_mining = True
                self.logger.info("KAIG SURVIVAL NOT MET — forcing aggressive mining")
            cycle = event_data.get("cycle", 0)
            if cycle <= 1 or cycle % 10 == 0:
                self.logger.info(
                    "KAIG Trading Directive → Mining: survival=%s | "
                    "price_floor=$%.2f (%s ATH) | profit=$%.2f | ultimate=$2T",
                    "MET" if survival_met else "NOT MET",
                    pf.get("current_ath_price_usd", 0),
                    pf.get("current_ath_coin", "BTC"),
                    event_data.get("profit_total_usd", 0),
                )
        except Exception as e:
            self.logger.error(f"Error handling KAIG trading directive in mining: {e}")

    async def _handle_kaig_ath_update(self, event_data):
        """Handle new crypto ATH detection — KAIG price floor raised."""
        try:
            if not isinstance(event_data, dict):
                return
            self.logger.warning(
                "Mining: NEW CRYPTO ATH — %s at $%s. KAIG price floor raised.",
                event_data.get("new_ath_coin", ""),
                f"{event_data.get('new_ath_price', 0):,.2f}",
            )
        except Exception as e:
            self.logger.error(f"Error handling kaig.ath.update in mining: {e}")

    async def _handle_identity_changed(self, event_data):
        """Handle token rebrand — mining rewards and balances are preserved.
        All earnings tracked by wallet address, not token name. Zero loss."""
        if isinstance(event_data, dict):
            self.logger.warning(
                "MiningIntelligence: TOKEN REBRANDED %s → %s. "
                "All mining rewards and balances preserved.",
                event_data.get("old_ticker", "?"),
                event_data.get("new_ticker", "?"))

    async def _handle_status_request(self, event):
        """
        Handle system status request events.
        
        This method responds to status requests from other components or the
        system management interface with the current status of the Mining Intelligence component.
        
        Args:
            event: The event data containing the status request information
        """
        try:
            self.logger.debug("Handling status request")
            
            # Extract request information
            request_id = event.get("request_id", str(uuid.uuid4()))
            requested_data = event.get("requested_data", ["all"])
            
            # Prepare status information
            status_data = {
                "component": self.component_name,
                "status": "active" if self._initialized else "initializing",
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id,
                "trading_system_readiness": self._trading_system_readiness,
            }
            
            # Add detailed information if requested
            if "all" in requested_data or "targets" in requested_data:
                status_data["target_coins"] = len(self.target_coins)
                status_data["top_targets"] = [
                    {"symbol": coin.symbol, "score": coin.profitability_score}
                    for coin in sorted(self.target_coins, key=lambda x: x.profitability_score, reverse=True)[:3]
                ] if self.target_coins else []
            
            if "all" in requested_data or "airdrops" in requested_data:
                status_data["airdrop_opportunities"] = len(self.airdrop_opportunities)
                status_data["active_airdrops"] = len([a for a in self.airdrop_opportunities if a.status == "in_progress"])
            
            if "all" in requested_data or "config" in requested_data:
                status_data["config"] = {
                    "aggressive_mining": self.aggressive_mining,
                    "auto_adjust_mining": self.auto_adjust_mining,
                    "parallel_mining_active": self.parallel_mining_active,
                    "auto_farm_airdrops": self.auto_farm_airdrops
                }
            
            # Publish status response
            if self.event_bus:
                await self.event_bus.publish("system.status_response", status_data)
                
            # Update mining statistics display
            await self._update_mining_statistics_display()
                
        except Exception as e:
            self.logger.error(f"Error handling status request: {e}")
            self.logger.error(traceback.format_exc())

    async def _handle_trading_system_readiness(self, event_data):
        """Keep mining intelligence synchronized with global trading readiness."""
        try:
            if isinstance(event_data, dict):
                self._trading_system_readiness = {
                    "state": str(event_data.get("state", "UNKNOWN")).upper(),
                    "auto_trade_started": bool(event_data.get("auto_trade_started", False)),
                    "analysis_ready": bool(event_data.get("analysis_ready", False)),
                    "reason": event_data.get("reason", ""),
                    "timestamp": event_data.get("timestamp"),
                }
        except Exception as e:
            self.logger.error(f"Error handling trading system readiness in mining intelligence: {e}")
    
    async def _update_mining_statistics_display(self):
        """
        Update the mining statistics display with current information.
        
        This method sends updated mining statistics to the dashboard or GUI
        for display to the user.
        
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            self.logger.debug("Updating mining statistics display")
            
            # Skip if mining dashboard is not available
            if not self.mining_dashboard:
                return True
                
            # Prepare statistics for display
            display_data = {
                "timestamp": datetime.now().isoformat(),
                "target_coins": len(self.target_coins),
                "active_airdrops": len([a for a in self.airdrop_opportunities if a.status == "in_progress"]),
                "mining_stats": self.mining_stats,
                "top_coins": [
                    {
                        "symbol": coin.symbol,
                        "algorithm": coin.algorithm.value if hasattr(coin.algorithm, "value") else str(coin.algorithm),
                        "profitability": coin.profitability_score,
                        "progress": (coin.current_amount / coin.target_amount) * 100 if coin.target_amount > 0 else 0
                    }
                    for coin in sorted(self.target_coins, key=lambda x: x.profitability_score, reverse=True)[:5]
                ] if self.target_coins else []
            }
            
            # Send to dashboard via event bus
            if self.event_bus:
                await self.event_bus.publish("dashboard.mining_statistics_update", {
                    "component": self.component_name,
                    "data": display_data
                })
                
            return True
                
        except Exception as e:
            self.logger.error(f"Error updating mining statistics display: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _optimization_loop(self):
        """
        Background task for continuous mining optimization.
        
        This method runs in the background and periodically performs
        optimization tasks for mining operations.
        """
        try:
            self.logger.info("Starting mining optimization loop")
            
            while True:
                # Skip if not initialized or component is shutting down
                if not self._initialized:
                    await asyncio.sleep(10)  # Check again in 10 seconds
                    continue
                    
                # Update mining statistics
                await self._update_mining_statistics_display()
                
                # CRITICAL: Publish intelligence updates to GUI (mining_frame.py subscribes to these)
                if self.event_bus:
                    # Publish mining intelligence update
                    await self.event_bus.publish("mining.intelligence.update", {
                        "type": "optimization_cycle",
                        "status": "active",
                        "target_coins": len(self.target_coins),
                        "active_algorithms": [c.algorithm.value for c in self.target_coins[:5]] if self.target_coins else [],
                        "aggressive_mining": self.aggressive_mining,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Publish recommendations if we have target coins
                    if self.target_coins:
                        recommendations = []
                        for coin in sorted(self.target_coins, key=lambda x: x.profitability_score, reverse=True)[:5]:
                            recommendations.append({
                                "symbol": coin.symbol,
                                "action": "mine",
                                "priority": coin.priority,
                                "score": coin.profitability_score,
                                "reason": f"High profitability score: {coin.profitability_score:.2f}"
                            })
                        await self.event_bus.publish("mining.intelligence.recommendation", {
                            "recommendations": recommendations,
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # Publish profit prediction
                    await self.event_bus.publish("mining.intelligence.profit_prediction", {
                        "prediction_data": [
                            {"symbol": c.symbol, "daily_profit": c.daily_emission * c.profitability_score}
                            for c in self.target_coins[:10]
                        ] if self.target_coins else [],
                        "confidence": 0.75,
                        "timestamp": datetime.now().isoformat()
                    })
                
                # Perform hardware optimization if enabled
                if self.auto_adjust_mining:
                    await self._optimize_hardware_settings()
                
                # Monitor mining performance
                await self._monitor_parallel_mining_performance()
                
                # Discover new mining opportunities periodically
                current_time = datetime.now()
                hour_of_day = current_time.hour
                
                # Run discovery during off-peak hours (typically night time)
                if hour_of_day >= 22 or hour_of_day <= 4:
                    await self._discover_new_mining_opportunities()
                
                # Collect mining rewards if enabled
                if self.auto_collect_rewards:
                    await self._collect_mining_rewards()
                
                # Update mining strategies based on current market conditions
                await self._update_mining_strategies()
                
                # Optimize parallel mining distribution if active
                if self.parallel_mining_active:
                    await self._optimize_parallel_mining_distribution()
                
                # Sleep for the configured interval before next optimization cycle
                await asyncio.sleep(self.optimization_interval)
                
        except asyncio.CancelledError:
            self.logger.info("Mining optimization loop cancelled")
        except Exception as e:
            self.logger.error(f"Error in mining optimization loop: {e}")
            self.logger.error(traceback.format_exc())
            # Try to restart the loop after a delay
            await asyncio.sleep(30)
            self.optimization_task = asyncio.create_task(self._optimization_loop())
        self.logger.info("Starting mining optimization loop")
        
        while True:
            try:
                # Wait for the specified interval
                await asyncio.sleep(self.optimization_interval)
                
                # Skip if not initialized
                if not self._initialized:
                    continue
                    
                self.logger.debug("Running optimization cycle")
                
                # Monitor mining performance
                await self._monitor_parallel_mining_performance()
                
                # Optimize hardware settings
                await self._optimize_hardware_settings()
                
                # Update mining strategies
                await self._update_mining_strategies()
                
                # Collect mining rewards if enabled
                if self.auto_collect_rewards:
                    await self._collect_mining_rewards()
                    
                # Update statistics display
                await self._update_mining_statistics_display()
                
            except asyncio.CancelledError:
                # Task was cancelled, exit cleanly
                self.logger.info("Optimization loop cancelled")
                break
                
            except Exception as e:
                self.logger.error(f"Error in optimization loop: {e}")
                self.logger.error(traceback.format_exc())
                # Continue the loop despite errors
    
    async def _airdrop_scanning_loop(self):
        """
        Background task for continuous airdrop scanning.
        
        This method runs in the background and periodically scans for
        new airdrop opportunities and updates progress on existing ones.
        """
        self.logger.info("Starting airdrop scanning loop")
        
        while True:
            try:
                # Wait for the specified interval
                await asyncio.sleep(self.airdrop_scanning_interval)
                
                # Skip if not initialized or if auto-farming is disabled
                if not self._initialized or not self.auto_farm_airdrops:
                    continue
                    
                self.logger.debug("Running airdrop scanning cycle")
                
                # Scan for new airdrops
                await self._scan_for_new_airdrops()
                
                # Update progress on existing airdrops
                await self._update_airdrop_progress()
                
            except asyncio.CancelledError:
                # Task was cancelled, exit cleanly
                self.logger.info("Airdrop scanning loop cancelled")
                break
                
            except Exception as e:
                self.logger.error(f"Error in airdrop scanning loop: {e}")
                self.logger.error(traceback.format_exc())
                # Continue the loop despite errors
    
    async def _portfolio_management_loop(self):
        """
        Background task for continuous portfolio management.
        
        This method runs in the background and periodically performs
        portfolio management tasks such as evaluating mining targets
        and trading underperforming assets.
        """
        self.logger.info("Starting portfolio management loop")
        
        while True:
            try:
                # Wait for the specified interval
                await asyncio.sleep(self.portfolio_update_interval)
                
                # Skip if not initialized
                if not self._initialized:
                    continue
                    
                self.logger.debug("Running portfolio management cycle")
                
                # Evaluate mining targets
                await self._evaluate_mining_targets()
                
                # Discover new mining opportunities
                await self._discover_new_mining_opportunities()
                
                # Trade underperforming assets if enabled
                if self.auto_trade_underperforming:
                    await self._trade_underperforming_assets()
                
            except asyncio.CancelledError:
                # Task was cancelled, exit cleanly
                self.logger.info("Portfolio management loop cancelled")
                break
                
            except Exception as e:
                self.logger.error(f"Error in portfolio management loop: {e}")
                self.logger.error(traceback.format_exc())
                # Continue the loop despite errors
    
    async def _ai_mining_focus_loop(self):
        self.logger.info("Starting AI mining focus optimization loop")
        
        while True:
            try:
                await asyncio.sleep(self.ai_mining_focus_interval)
                if not self._initialized:
                    continue
                if not self.thoth_ai:
                    continue
                brain = getattr(self.thoth_ai, "brain", None)
                if not brain:
                    continue
                try:
                    if hasattr(brain, "is_available") and not brain.is_available:
                        continue
                except Exception:
                    pass
                prompt = (
                    "Act as the Kingdom AI mining optimization brain. "
                    "Use your mining analytics tools to select the best mix of coins to mine "
                    "for maximum profitability and diversity, and then apply the new focus "
                    "using your auto_set_mining_focus tool. "
                    "Do not ask questions; decide and apply the new focus directly."
                )
                try:
                    response = await brain.process_text(
                        prompt,
                        task="mining",
                        max_iterations=4
                    )
                    if not getattr(response, "success", False):
                        self.logger.debug(
                            f"AI mining focus optimization cycle did not succeed: {getattr(response, 'error', 'unknown error')}"
                        )
                except Exception as e:
                    self.logger.error(f"Error during AI mining focus optimization cycle: {e}")
                    self.logger.error(traceback.format_exc())
            except asyncio.CancelledError:
                self.logger.info("AI mining focus optimization loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in AI mining focus optimization loop: {e}")
                self.logger.error(traceback.format_exc())
    
    async def _handle_difficulty_update(self, event):
        """
        Handle difficulty update events from blockchain connector.
        
        Args:
            event: The event data containing difficulty update information
        """
        try:
            self.logger.debug("Handling difficulty update event")
            
            # Extract relevant data
            data = event.get("data", {})
            coin_symbol = data.get("symbol")
            new_difficulty = data.get("difficulty")
            timestamp = data.get("timestamp")
            
            if not coin_symbol or new_difficulty is None:
                self.logger.warning("Received invalid difficulty update data")
                return
                
            # Update internal coin data
            if coin_symbol not in self.coin_data:
                self.coin_data[coin_symbol] = {}
                
            # Store previous difficulty for trend calculation
            previous_difficulty = self.coin_data[coin_symbol].get("difficulty", new_difficulty)
            
            # Update difficulty value
            self.coin_data[coin_symbol]["difficulty"] = new_difficulty
            self.coin_data[coin_symbol]["difficulty_updated"] = timestamp or datetime.now().isoformat()
            
            # Calculate difficulty trend (-1 to 1 scale)
            if previous_difficulty > 0:
                trend = (new_difficulty - previous_difficulty) / previous_difficulty
                # Clamp trend to range [-1, 1]
                difficulty_trend = max(-1.0, min(1.0, trend))
                self.coin_data[coin_symbol]["difficulty_trend"] = difficulty_trend
                
                self.logger.info(f"Updated difficulty for {coin_symbol}: {new_difficulty:.2f} (trend: {difficulty_trend:.2f})")
            
            # Update profitability scores if this coin is in our target list
            for coin in self.target_coins:
                if coin.symbol == coin_symbol:
                    # Store old score for logging
                    old_score = coin.profitability_score
                    # Re-calculate profitability with new difficulty
                    await self._update_coin_profitability_scores()
                    self.logger.info(f"Updated profitability score for {coin_symbol}: {old_score:.2f} -> {coin.profitability_score:.2f}")
                    break
            
            # If parallel mining is active, optimize distribution
            if self.parallel_mining_active:
                # Apply the latest information to optimize mining distribution
                await self._optimize_parallel_mining_distribution()
        except Exception as e:
            self.logger.error(f"Error handling difficulty update event: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _handle_reward_update(self, event):
        """
        Handle mining reward update events.
        
        Args:
            event: The event data containing reward update information
        """
        try:
            self.logger.debug("Handling reward update event")
            
            # Extract relevant data
            data = event.get("data", {})
            coin_symbol = data.get("symbol")
            reward_amount = data.get("amount")
            timestamp = data.get("timestamp")
            pool = data.get("pool", "unknown")
            
            if not coin_symbol or reward_amount is None:
                self.logger.warning("Received invalid reward update data")
                return
                
            # Update internal rewards tracking
            if coin_symbol not in self.mining_rewards_by_coin:
                self.mining_rewards_by_coin[coin_symbol] = []
                
            # Add new reward record
            self.mining_rewards_by_coin[coin_symbol].append({
                "amount": reward_amount,
                "timestamp": timestamp or datetime.now().isoformat(),
                "pool": pool,
                "collected": False
            })
            
            self.logger.info(f"New mining reward for {coin_symbol}: {reward_amount} from {pool}")
            
            # Update coin amount for target coins
            for coin in self.target_coins:
                if coin.symbol == coin_symbol:
                    coin.current_amount += reward_amount
                    coin.last_mined = datetime.now()
                    self.logger.info(f"Updated {coin_symbol} amount: {coin.current_amount:.2f}/{coin.target_amount:.2f}")
                    break
                    
            # If auto-collect is enabled, schedule collection
            if self.auto_collect_rewards and sum(r["amount"] for r in self.mining_rewards_by_coin[coin_symbol] if not r["collected"]) > 5.0:
                self.logger.info(f"Scheduling automatic collection of {coin_symbol} rewards")
                # We'll let the optimization loop handle the actual collection
            
        except Exception as e:
            self.logger.error(f"Error handling reward update event: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _handle_algorithm_performance(self, event):
        """
        Handle algorithm performance update events.
        
        Args:
            event: The event data containing algorithm performance information
        """
        try:
            self.logger.debug("Handling algorithm performance event")
            
            # Extract relevant data
            data = event.get("data", {})
            algorithm = data.get("algorithm")
            hashrate = data.get("hashrate")
            power_usage = data.get("power_usage")
            coins_per_day = data.get("coins_per_day")
            value_per_day = data.get("value_per_day")
            
            if not algorithm:
                self.logger.warning("Received invalid algorithm performance data")
                return
                
            # Calculate efficiency
            efficiency = value_per_day / max(1.0, power_usage) if power_usage and value_per_day else 0.0
            
            # Update mining stats
            self.mining_stats[algorithm] = MiningStats(
                algorithm=algorithm,
                hashrate=hashrate or 0.0,
                power_usage=power_usage or 0.0,
                coins_per_day=coins_per_day or 0.0,
                value_per_day=value_per_day or 0.0,
                efficiency=efficiency,
                timestamp=datetime.now(),
                competition_level=data.get("competition_level", 0.0),
                network_difficulty_trend=data.get("difficulty_trend", 0.0)
            )
            
            self.logger.info(f"Updated performance stats for {algorithm}: {hashrate:.2f} H/s, ${value_per_day:.2f}/day, {efficiency:.4f} $/W")
            
            # If we've collected stats for all algorithms, optimize hardware settings
            if self.auto_adjust_mining and len(self.mining_stats) >= len([c for c in self.target_coins if c.profitability_score > 0]):
                await self._optimize_hardware_settings()
                
        except Exception as e:
            self.logger.error(f"Error handling algorithm performance event: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _handle_price_update(self, event):
        """
        Handle price update events from market data provider.
        
        Args:
            event: The event data containing price update information
        """
        try:
            self.logger.debug("Handling price update event")
            
            # Extract relevant data
            data = event.get("data", {})
            coin_symbol = data.get("symbol")
            new_price = data.get("price")
            timestamp = data.get("timestamp")
            
            if not coin_symbol or new_price is None:
                self.logger.warning("Received invalid price update data")
                return
                
            # Update internal coin data
            if coin_symbol not in self.coin_data:
                self.coin_data[coin_symbol] = {}
                
            # Store previous price for trend calculation
            previous_price = self.coin_data[coin_symbol].get("price", new_price)
            
            # Update price value
            self.coin_data[coin_symbol]["price"] = new_price
            self.coin_data[coin_symbol]["price_updated"] = timestamp or datetime.now().isoformat()
            
            # Calculate price trend (-1 to 1 scale)
            if previous_price > 0:
                trend = (new_price - previous_price) / previous_price
                # Clamp trend to range [-1, 1]
                price_trend = max(-1.0, min(1.0, trend))
                self.coin_data[coin_symbol]["price_trend"] = price_trend
                
                # Only log significant price changes
                if abs(price_trend) > 0.02:  # 2% change
                    self.logger.info(f"Significant price change for {coin_symbol}: ${previous_price:.4f} -> ${new_price:.4f} ({price_trend*100:.1f}%)")
            
            # Update profitability scores if this coin is in our target list
            for coin in self.target_coins:
                if coin.symbol == coin_symbol:
                    # Re-calculate profitability with new price
                    # We call this once to update all coins
                    await self._update_coin_profitability_scores()
                    break
            
            # If parallel mining is active, may need to re-optimize
            if self.parallel_mining_active and abs(trend if 'trend' in locals() else 0) > 0.05:  # 5% change
                await self._optimize_parallel_mining_distribution()
                
        except Exception as e:
            self.logger.error(f"Error handling price update event: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _handle_trend_update(self, event):
        """
        Handle market trend update events.
        
        Args:
            event: The event data containing trend update information
        """
        try:
            self.logger.debug("Handling trend update event")
            
            # Extract relevant data
            data = event.get("data", {})
            coin_symbol = data.get("symbol")
            trend_data = data.get("trends", {})
            timestamp = data.get("timestamp")
            
            if not coin_symbol or not trend_data:
                self.logger.warning("Received invalid trend update data")
                return
                
            # Update internal coin data
            if coin_symbol not in self.coin_data:
                self.coin_data[coin_symbol] = {}
                
            # Update trend data
            for trend_key, trend_value in trend_data.items():
                self.coin_data[coin_symbol][f"trend_{trend_key}"] = trend_value
            
            self.coin_data[coin_symbol]["trends_updated"] = timestamp or datetime.now().isoformat()
            
            # Log significant trend changes
            if "overall" in trend_data and abs(trend_data["overall"]) > 0.7:  # Strong trend
                direction = "bullish" if trend_data["overall"] > 0 else "bearish"
                self.logger.info(f"Strong {direction} trend detected for {coin_symbol}: {trend_data['overall']:.2f}")
                
            # If trading integration is enabled, check for trading signals
            if self.auto_trade_underperforming and self.trading_intelligence and "overall" in trend_data:
                # Strong negative trend might trigger trading of underperforming assets
                if trend_data["overall"] < -0.7:
                    for coin in self.target_coins:
                        if coin.symbol == coin_symbol and coin.current_amount > 10.0:
                            self.logger.info(f"Strong negative trend for {coin_symbol} may trigger trading decision")
                            # We'll let the portfolio management loop handle the actual trading
                            break
                
        except Exception as e:
            self.logger.error(f"Error handling trend update event: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _handle_airdrop_eligibility(self, event):
        """
        Handle airdrop eligibility check result events.
        
        Args:
            event: The event data containing eligibility check results
        """
        try:
            self.logger.debug("Handling airdrop eligibility event")
            
            # Extract relevant data
            data = event.get("data", {})
            airdrop_id = data.get("airdrop_id")
            is_eligible = data.get("eligible", False)
            reasons = data.get("reasons", [])
            wallets = data.get("eligible_wallets", [])
            
            if not airdrop_id:
                self.logger.warning("Received invalid airdrop eligibility data")
                return
                
            # Find the corresponding airdrop opportunity
            airdrop = next((a for a in self.airdrop_opportunities if a.id == airdrop_id), None)
            if not airdrop:
                self.logger.warning(f"Cannot find airdrop with ID {airdrop_id}")
                return
                
            # Update eligibility status
            airdrop.eligibility_checked = True
            
            if is_eligible:
                self.logger.info(f"Eligible for airdrop: {airdrop.project} with {len(wallets)} wallets")
                airdrop.status = "in_progress"
                airdrop.wallets_used = wallets
                airdrop.completion_percentage = 10.0  # Starting progress
                
                # If auto-farming is enabled, start the farming process
                if self.auto_farm_airdrops and self.event_bus:
                    await self.event_bus.publish("airdrop.start_farming", {
                        "airdrop_id": airdrop.id,
                        "project": airdrop.project,
                        "wallets": wallets,
                        "timestamp": datetime.now().isoformat()
                    })
            else:
                self.logger.info(f"Not eligible for airdrop: {airdrop.project}. Reasons: {', '.join(reasons)}")
                airdrop.status = "ineligible"
                
        except Exception as e:
            self.logger.error(f"Error handling airdrop eligibility event: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _handle_airdrop_opportunity(self, event):
        """
        Handle airdrop opportunity discovery events.
        
        Args:
            event: The event data containing airdrop information
        """
        try:
            # Process airdrop opportunity event
            airdrop_data = event.get('data', {})
            
            # Skip if no valid data
            if not airdrop_data:
                self.logger.warning("Received airdrop opportunity event with no data")
                return
                
            # Create airdrop opportunity object
            airdrop = AirdropOpportunity(
                id=airdrop_data.get("id", str(uuid.uuid4())),
                project=airdrop_data.get("project", "Unknown Project"),
                chain=airdrop_data.get("chain", "ethereum"),
                estimated_value=float(airdrop_data.get("estimated_value", 0.0)),
                requirements=airdrop_data.get("requirements", []),
                deadline=datetime.fromisoformat(airdrop_data["deadline"]) if "deadline" in airdrop_data else None,
                url=airdrop_data.get("url", ""),
                confidence=float(airdrop_data.get("confidence", 0.5)),
                status="discovered"
            )
            
            # Add to opportunities list if not already present
            if airdrop.id not in [op.id for op in self.airdrop_opportunities]:
                self.airdrop_opportunities.append(airdrop)
                self.logger.info(f"New airdrop opportunity discovered: {airdrop.project} (est. value: ${airdrop.estimated_value:.2f})")
                
                # If auto-farming is enabled, check eligibility
                if self.auto_farm_airdrops:
                    self.logger.info(f"Auto-farming enabled, checking eligibility for {airdrop.project}")
                    
                    # Mark for eligibility check
                    airdrop.status = "eligibility_check"
                    
                    # Request eligibility check via event bus
                    if self.event_bus:
                        await self.event_bus.publish("airdrop.check_eligibility", {
                            "airdrop_id": airdrop.id,
                            "project": airdrop.project,
                            "requirements": airdrop.requirements,
                            "timestamp": datetime.now().isoformat()
                        })
        except Exception as e:
            self.logger.error(f"Error handling airdrop opportunity: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _handle_airdrop_scan_request(self, event):
        """Handle airdrop scan request from GUI - load and publish airdrops from config.
        
        SOTA 2026 FIX: This handler loads airdrops from config/airdrops.json and
        publishes them to the GUI for display in the Airdrop Farming tab.
        """
        try:
            self.logger.info("🔍 Processing airdrop scan request...")
            
            # Load airdrops from config file
            import json
            from pathlib import Path
            
            config_path = Path("config/airdrops.json")
            if not config_path.exists():
                self.logger.warning("❌ config/airdrops.json not found")
                return
            
            with open(config_path, 'r') as f:
                airdrop_config = json.load(f)
            
            airdrops = airdrop_config.get("airdrops", [])
            scan_settings = airdrop_config.get("scan_settings", {})
            
            self.logger.info(f"📋 Found {len(airdrops)} configured airdrops")
            
            # Publish each enabled airdrop to the GUI
            for airdrop in airdrops:
                if airdrop.get("enabled", False):
                    # Publish airdrop discovery event
                    if self.event_bus:
                        await self.event_bus.publish("airdrop.discovery", {
                            "name": airdrop.get("name", "Unknown"),
                            "chain": airdrop.get("chain", "unknown"),
                            "wallet_network": airdrop.get("wallet_network", "ethereum"),
                            "description": airdrop.get("description", ""),
                            "estimated_value": airdrop.get("estimated_value", "Unknown"),
                            "status": "active" if airdrop.get("enabled") else "inactive",
                            "requirements": airdrop.get("claim", {}).get("notes", "Check eligibility"),
                            "config": airdrop,
                            "timestamp": time.time()
                        })
            
            # Publish scan complete event
            if self.event_bus:
                await self.event_bus.publish("airdrop.scan.complete", {
                    "total_airdrops": len(airdrops),
                    "enabled_airdrops": sum(1 for a in airdrops if a.get("enabled", False)),
                    "chains": list(set(a.get("chain", "unknown") for a in airdrops)),
                    "timestamp": time.time()
                })
            
            self.logger.info(f"✅ Airdrop scan complete - {len(airdrops)} airdrops processed")
            
        except Exception as e:
            self.logger.error(f"Error handling airdrop scan request: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _handle_airdrop_register_requested(self, event):
        """Handle direct airdrop registration requests from the GUI/blockchain connector.
        
        This method receives structured payloads from BlockchainConnector.register_for_airdrop
        via the EventBus topic "airdrop.register.requested" and coordinates chain-aware
        registration using WalletManager and kingdomweb3_v2 metadata. It emits
        "airdrop.register.completed" or "airdrop.register.failed" so the GUI and
        other components can update in real time.
        """
        try:
            # Normalize event payload: support both {data: {...}} and direct dict styles
            payload = event or {}
            if isinstance(payload, dict) and "airdrop_name" not in payload and "data" in payload:
                inner = payload.get("data")
                if isinstance(inner, dict):
                    payload = inner
            
            airdrop_config = payload.get("config") or {}
            claim_config = airdrop_config.get("claim") or {}
            airdrop_name = payload.get("airdrop_name") or payload.get("name")
            network = payload.get("network") or "ethereum"
            wallet_network = payload.get("wallet_network") or network
            wallet_address = payload.get("wallet_address")
            rpc_url = payload.get("rpc_url")
            is_evm = payload.get("is_evm", True)
            
            if not airdrop_name:
                self.logger.warning("Received airdrop.register.requested with no airdrop_name")
                return
            
            self.logger.info(
                "Handling airdrop.register.requested for %s on network=%s (wallet_network=%s)",
                airdrop_name,
                network,
                wallet_network,
            )
            
            # Ensure WalletManager is available to resolve wallet addresses
            if not wallet_address:
                try:
                    if not self.wallet_manager:
                        from core.wallet_manager import WalletManager
                        self.wallet_manager = WalletManager(event_bus=self.event_bus)
                    wallet_address = self.wallet_manager.get_address(wallet_network)
                except Exception as wallet_error:
                    self.logger.error(f"Failed to resolve wallet address for {wallet_network}: {wallet_error}")
                    if self.event_bus:
                        await self.event_bus.publish("airdrop.register.failed", {
                            "airdrop_name": airdrop_name,
                            "network": network,
                            "wallet_network": wallet_network,
                            "wallet_address": None,
                            "error": f"wallet_resolution_failed: {wallet_error}",
                            "timestamp": datetime.now().isoformat(),
                        })
                    return
            
            tx_hash = None
            error_msg = None
            success = False
            
            # Attach kingdomweb3_v2 network metadata when available
            try:
                from kingdomweb3_v2 import get_network_config, create_web3_instance, web3_available
                net_conf = get_network_config(network) or {}
                if rpc_url is None:
                    rpc_url = net_conf.get("rpc_url")
                if "is_evm" in net_conf and "is_evm" not in payload:
                    is_evm = net_conf.get("is_evm", is_evm)
            except Exception as e:
                self.logger.error(f"Error importing kingdomweb3_v2 for airdrop registration: {e}")
                net_conf = {}
                web3_available = False
            
            # For EVM chains, attempt a connectivity check via Web3.
            if is_evm:
                if not rpc_url or "YOUR_PROJECT_ID" in str(rpc_url):
                    error_msg = "rpc_url_not_configured_for_evm_airdrop"
                else:
                    try:
                        if web3_available:
                            web3_instance = create_web3_instance(rpc_url, network_name=network)
                            # Verify connectivity to the RPC endpoint
                            if hasattr(web3_instance, "is_connected") and not web3_instance.is_connected():
                                raise RuntimeError("web3_not_connected")
                        # Attempt actual registration transaction
                        # Get wallet private key for signing
                        from core.wallet_manager import WalletManager
                        wallet_mgr = WalletManager(event_bus=self.event_bus)
                        
                        wallet_info = wallet_mgr.get_wallet_by_address(wallet_address)
                        if not wallet_info:
                            raise RuntimeError("wallet_not_found")
                        
                        # Get contract ABI and address from airdrop config
                        contract_address = claim_config.get("contract_address")
                        if not contract_address:
                            raise RuntimeError("contract_address_not_in_config")
                        
                        # Build registration transaction
                        # This is a generic implementation - specific airdrops may need custom ABIs
                        registration_abi = claim_config.get("abi") or [
                            {
                                "inputs": [{"name": "user", "type": "address"}],
                                "name": "register",
                                "outputs": [{"name": "", "type": "bool"}],
                                "stateMutability": "nonpayable",
                                "type": "function"
                            }
                        ]
                        
                        contract = web3_instance.eth.contract(
                            address=contract_address,
                            abi=registration_abi
                        )
                        
                        # Build and send transaction
                        nonce = web3_instance.eth.get_transaction_count(wallet_address)
                        gas_price = web3_instance.eth.gas_price
                        
                        tx = contract.functions.register(wallet_address).build_transaction({
                            "from": wallet_address,
                            "nonce": nonce,
                            "gasPrice": gas_price,
                            "chainId": chain_id
                        })
                        
                        # Estimate gas
                        gas_estimate = web3_instance.eth.estimate_gas(tx)
                        tx["gas"] = gas_estimate
                        
                        # Sign transaction (requires wallet private key access)
                        # Note: In production, this should use secure key management
                        private_key = wallet_info.get("private_key")
                        if not private_key:
                            # Return pending status if private key not available
                            self.logger.warning(f"Private key not available for wallet {wallet_address} - registration pending")
                            if self.event_bus:
                                await self.event_bus.publish("airdrop.register.pending", {
                                    "airdrop_name": airdrop_name,
                                    "network": network,
                                    "wallet_address": wallet_address,
                                    "status": "pending_private_key",
                                    "timestamp": datetime.now().isoformat(),
                                })
                            return  # Exit early with pending status
                        
                        from eth_account import Account
                        account = Account.from_key(private_key)
                        signed_tx = account.sign_transaction(tx)
                        
                        # Send transaction
                        tx_hash_bytes = web3_instance.eth.send_raw_transaction(signed_tx.rawTransaction)
                        tx_hash = web3_instance.to_hex(tx_hash_bytes)
                        
                        # Wait for confirmation (with timeout)
                        receipt = web3_instance.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                        success = receipt.status == 1
                    except Exception as e:
                        error_msg = f"evm_registration_failed: {e}"
            else:
                # Non-EVM chains (Solana, XRP, etc.) require chain-specific SDKs and
                # program/contract details that are not defined in this repository.
                error_msg = f"non_evm_registration_not_implemented_for_{network}"
            
            # Emit result events for GUI and other components
            if success:
                if self.event_bus:
                    await self.event_bus.publish("airdrop.register.completed", {
                        "airdrop_name": airdrop_name,
                        "network": network,
                        "wallet_network": wallet_network,
                        "wallet_address": wallet_address,
                        "tx_hash": tx_hash,
                        "config": airdrop_config,
                        "claim": claim_config,
                        "timestamp": datetime.now().isoformat(),
                    })
                self.logger.info(
                    "Airdrop registration completed for %s on %s with wallet %s",
                    airdrop_name,
                    network,
                    wallet_address,
                )
            else:
                if self.event_bus:
                    await self.event_bus.publish("airdrop.register.failed", {
                        "airdrop_name": airdrop_name,
                        "network": network,
                        "wallet_network": wallet_network,
                        "wallet_address": wallet_address,
                        "error": error_msg or "unknown_error",
                        "config": airdrop_config,
                        "claim": claim_config,
                        "timestamp": datetime.now().isoformat(),
                    })
                self.logger.warning(
                    "Airdrop registration failed for %s on %s (wallet=%s, error=%s)",
                    airdrop_name,
                    network,
                    wallet_address,
                    error_msg,
                )
        except Exception as e:
            self.logger.error(f"Error handling airdrop.register.requested: {e}")
            self.logger.error(traceback.format_exc())
            if self.event_bus:
                try:
                    await self.event_bus.publish("airdrop.register.failed", {
                        "airdrop_name": (event or {}).get("airdrop_name") if isinstance(event, dict) else None,
                        "network": (event or {}).get("network") if isinstance(event, dict) else None,
                        "wallet_network": (event or {}).get("wallet_network") if isinstance(event, dict) else None,
                        "wallet_address": (event or {}).get("wallet_address") if isinstance(event, dict) else None,
                        "error": f"exception: {e}",
                        "timestamp": datetime.now().isoformat(),
                    })
                except Exception:
                    # Best-effort only
                    pass
        
    async def _monitor_parallel_mining_performance(self):
        """
        Monitor the performance of parallel mining operations.
        
        This method collects and analyzes data about mining performance
        across different algorithms and hardware configurations.
        
        Returns:
            bool: True if monitoring was successful, False otherwise
        """
        try:
            self.logger.debug("Monitoring parallel mining performance")
            
            if not self.parallel_mining_active:
                return True
                
            # Request current mining statistics from mining system
            if self.event_bus and self.core_mining_system:
                # Request statistics via event bus
                await self.event_bus.publish("mining.request_statistics", {
                    "requestor": "mining_intelligence",
                    "timestamp": datetime.now().isoformat()
                })
                
                # Wait for real mining statistics from mining system
                # If no real data available, return empty stats (honest "awaiting data")
                if not self.mining_stats or len(self.mining_stats) == 0:
                    # No mock data - return empty stats to indicate awaiting real data
                    logger.info("Mining intelligence: Awaiting real mining statistics from mining system")
                    # Stats will be populated when mining system publishes real data
                    return
            
            # Log performance data
            if self.mining_stats:
                top_performers = sorted(
                    self.mining_stats.values(), 
                    key=lambda x: x.value_per_day, 
                    reverse=True
                )[:3]
                
                self.logger.info("Top performing mining algorithms:")
                for i, stats in enumerate(top_performers, 1):
                    self.logger.info(
                        f"{i}. {stats.algorithm}: ${stats.value_per_day:.2f}/day, "
                        f"{stats.efficiency:.4f} $/watt"
                    )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error monitoring mining performance: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def _optimize_hardware_settings(self):
        """
        Optimize hardware settings for mining operations.
        
        This method adjusts clock speeds, power limits, and other hardware
        settings to maximize mining efficiency based on current conditions.
        
        Returns:
            bool: True if optimization was successful, False otherwise
        """
        try:
            self.logger.debug("Optimizing hardware settings for mining operations")
            
            # Skip if no core mining system is available
            if not self.core_mining_system:
                self.logger.warning("No core mining system available for hardware optimization")
                return False
                
            # Get current hardware settings and performance metrics
            hardware_status = await self.core_mining_system.get_hardware_status()
            
            if not hardware_status:
                self.logger.warning("Unable to retrieve hardware status for optimization")
                return False
                
            # Extract hardware information
            devices = hardware_status.get('devices', [])
            
            if not devices:
                self.logger.warning("No mining devices found for optimization")
                return False
                
            # Iterate through each device and optimize settings
            optimized_devices = 0
            for device in devices:
                device_id = device.get('id')
                device_type = device.get('type')
                algorithm = device.get('current_algorithm')
                current_hashrate = device.get('hashrate', 0)
                power_usage = device.get('power_usage', 0)
                temperature = device.get('temperature', 0)
                fan_speed = device.get('fan_speed', 0)
                
                # Skip devices without basic information
                if not all([device_id, device_type, algorithm]):
                    continue
                    
                # Calculate current efficiency (hashrate per watt)
                current_efficiency = current_hashrate / max(1, power_usage)
                
                # Determine optimal settings based on device type, algorithm, and current conditions
                optimal_settings = self._calculate_optimal_settings(
                    device_type, algorithm, current_hashrate, power_usage, temperature, fan_speed
                )
                
                if not optimal_settings:
                    self.logger.debug(f"No optimization available for device {device_id}")
                    continue
                    
                # Apply optimized settings
                success = await self.core_mining_system.apply_device_settings(
                    device_id, optimal_settings
                )
                
                if success:
                    optimized_devices += 1
                    self.logger.info(f"Applied optimized settings to device {device_id} for {algorithm}")
                    
                    # Update mining statistics for this device
                    if device_id in self.mining_stats:
                        self.mining_stats[device_id]['efficiency'] = current_efficiency
                        self.mining_stats[device_id]['last_optimized'] = datetime.now().isoformat()
                        
            # Log optimization results
            if optimized_devices > 0:
                self.logger.info(f"Successfully optimized {optimized_devices} mining devices")
                return True
            else:
                self.logger.info("No devices were optimized in this cycle")
                return False
                
        except Exception as e:
            self.logger.error(f"Error optimizing hardware settings: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    def _calculate_optimal_settings(self, device_type, algorithm, current_hashrate, power_usage, temperature, fan_speed):
        """
        Calculate optimal settings for a mining device based on its characteristics and current performance.
        
        Args:
            device_type: Type of mining device (GPU, ASIC, etc.)
            algorithm: Current mining algorithm
            current_hashrate: Current hashrate
            power_usage: Current power consumption in watts
            temperature: Current temperature in Celsius
            fan_speed: Current fan speed percentage
            
        Returns:
            dict: Optimal settings for the device, or None if no optimization is possible
        """
        try:
            # Default optimization result
            optimal_settings = {}
            
            # Adjust settings based on device type
            if device_type.lower() == 'gpu':
                # GPU-specific optimization logic
                
                # Check if temperature is too high
                if temperature > 80:  # Celsius
                    # Lower power limit and increase fan speed for cooling
                    optimal_settings['power_limit'] = max(50, power_usage - 15)  # Reduce by 15W but not below 50W
                    optimal_settings['fan_speed'] = min(100, fan_speed + 15)     # Increase by 15% but not above 100%
                    
                elif temperature < 60:  # Celsius
                    # Temperature is low, can potentially increase power for more hashrate
                    # But only if efficiency is good
                    current_efficiency = current_hashrate / max(1, power_usage)
                    
                    if current_efficiency > 0.5:  # Arbitrary threshold for "good efficiency"
                        optimal_settings['power_limit'] = power_usage + 10  # Increase by 10W
                        optimal_settings['core_clock'] = '+50'  # Slight core clock boost
                        
                # Algorithm-specific optimizations
                if algorithm == MiningAlgorithm.ETHASH.value:
                    # Memory-intensive algorithm
                    optimal_settings['memory_clock'] = '+500'  # Memory overclock
                    
                elif algorithm == MiningAlgorithm.RANDOMX.value:
                    # CPU-intensive algorithm
                    optimal_settings['core_clock'] = '+100'  # Core clock boost
                    
                # Ensure fan control is enabled for GPU mining
                optimal_settings['fan_control'] = True
                
            elif device_type.lower() == 'asic':
                # ASIC-specific optimization logic
                
                # ASICs have fewer tunable parameters
                if temperature > 75:  # Celsius
                    # Implement cooling mode
                    optimal_settings['operating_mode'] = 'efficient'
                    
                elif temperature < 65:  # Celsius
                    # Can run in performance mode
                    optimal_settings['operating_mode'] = 'performance'
                else:
                    # Normal temperature range
                    optimal_settings['operating_mode'] = 'balanced'
                    
            return optimal_settings if optimal_settings else None
            
        except Exception as e:
            self.logger.error(f"Error calculating optimal settings: {e}")
            return None
            
    async def _scan_for_new_airdrops(self):
        """
        Scan for new airdrop opportunities.
        
        This method actively scans various sources to discover new airdrops
        that might be eligible for farming.
        
        Returns:
            bool: True if scanning was successful, False otherwise
        """
        try:
            self.logger.debug("Scanning for new airdrops")
            
            # Check if airdrop scanning is enabled
            if not self.auto_farm_airdrops:
                return True
                
            # In a real implementation, this would scan external sources
            # For now, we'll simulate the discovery process
            if self.event_bus:
                # Request airdrop data from external sources via the event bus
                await self.event_bus.publish("airdrop.scan_request", {
                    "requestor": "mining_intelligence",
                    "timestamp": datetime.now().isoformat()
                })
            
            # Log scan completion
            self.logger.info("Completed airdrop scan")
            return True
            
        except Exception as e:
            self.logger.error(f"Error scanning for airdrops: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def _update_airdrop_progress(self):
        """
        Update progress on existing airdrop opportunities.
        
        This method updates the status and completion percentage of
        existing airdrop opportunities being farmed.
        
        Returns:
            bool: True if updates were successful, False otherwise
        """
        try:
            self.logger.debug("Updating airdrop progress")
            
            # Skip if no airdrops to update
            if not self.airdrop_opportunities:
                return True
                
            # Update each in-progress airdrop
            for airdrop in self.airdrop_opportunities:
                if airdrop.status == "in_progress":
                    # In a real implementation, this would check actual progress
                    # For now, we'll simulate progress updates
                    if airdrop.completion_percentage < 100.0:
                        # Simulate progress by incrementing completion percentage
                        airdrop.completion_percentage += random.uniform(5.0, 15.0)
                        airdrop.completion_percentage = min(100.0, airdrop.completion_percentage)
                        
                        self.logger.info(f"Airdrop {airdrop.project} progress: {airdrop.completion_percentage:.1f}%")
                        
                        # Check if airdrop is completed
                        if airdrop.completion_percentage >= 100.0:
                            airdrop.status = "completed"
                            self.logger.info(f"Airdrop {airdrop.project} completed successfully")
                            
                            # Publish completion notification
                            if self.event_bus:
                                await self.event_bus.publish("airdrop.completed", {
                                    "id": airdrop.id,
                                    "project": airdrop.project,
                                    "estimated_value": airdrop.estimated_value,
                                    "timestamp": datetime.now().isoformat()
                                })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating airdrop progress: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def _evaluate_new_mining_opportunity(self, coin_symbol):
        """
        Evaluate if a newly discovered coin should be added as a mining target.
        
        Args:
            coin_symbol: Symbol of the coin to evaluate
            
        Returns:
            bool: True if the coin was added as a target, False otherwise
        """
        try:
            if coin_symbol not in self.coin_data:
                self.logger.warning(f"Cannot evaluate {coin_symbol}, no data available")
                return False
                
            # Get coin data
            coin_data = self.coin_data[coin_symbol]
            
            # Calculate initial profitability
            profitability = await self._calculate_initial_profitability(coin_data)
            
            # Only add coins with sufficient profitability
            if profitability > 10.0:  # Arbitrary threshold
                # Check if we already have this coin in targets
                for existing in self.target_coins:
                    if existing.symbol == coin_symbol:
                        self.logger.debug(f"{coin_symbol} already in mining targets")
                        return False
                        
                # Create a new coin target
                algorithm = self._determine_best_algorithm(coin_symbol)
                if not algorithm:
                    self.logger.warning(f"Could not determine mining algorithm for {coin_symbol}")
                    return False
                    
                new_target = CoinTarget(
                    symbol=coin_symbol,
                    name=coin_data.get('name', coin_symbol),
                    algorithm=algorithm,
                    profitability_score=profitability,
                    last_mined=None,
                    priority=1.0  # Default priority
                )
                
                # Add to target list
                self.target_coins.append(new_target)
                self.logger.info(f"Added {coin_symbol} to mining targets with profitability {profitability:.2f}")
                
                # Re-prioritize targets
                await self._prioritize_target_coins()
                return True
            else:
                self.logger.debug(f"Coin {coin_symbol} profitability {profitability:.2f} below threshold")
                return False
                
        except Exception as e:
            self.logger.error(f"Error evaluating new mining opportunity: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    def _determine_best_algorithm(self, coin_symbol):
        """
        Determine the best mining algorithm for a given coin.
        
        Args:
            coin_symbol: Symbol of the coin to evaluate
            
        Returns:
            MiningAlgorithm: The best algorithm to use, or None if unknown
        """
        # This would normally involve more complex logic based on blockchain data
        # For simplicity, we'll use a mapping of common coins to algorithms
        coin_to_algorithm = {
            'BTC': MiningAlgorithm.SHA256,
            'ETH': MiningAlgorithm.ETHASH,
            'LTC': MiningAlgorithm.SCRYPT,
            'ZEC': MiningAlgorithm.EQUIHASH,
            'XMR': MiningAlgorithm.RANDOMX,
            'KDA': MiningAlgorithm.KADENA,
            'KAS': MiningAlgorithm.KASPA,
            'ERG': MiningAlgorithm.ERGO
        }
        
        return coin_to_algorithm.get(coin_symbol.upper(), MiningAlgorithm.SHA256)  # Default to SHA256
            
    async def _evaluate_mining_targets(self):
        """
        Evaluate and update mining targets based on current market conditions.
        
        This method reviews the list of target coins, potentially adding new ones
        or removing underperforming ones based on market data and mining performance.
        
        Returns:
            bool: True if evaluation was successful, False otherwise
        """
        try:
            self.logger.debug("Evaluating mining targets")
            
            # Update profitability of current targets
            await self._update_coin_profitability_scores()
            
            # Check for coins that have reached their target amount
            completed_targets = [coin for coin in self.target_coins if coin.current_amount >= coin.target_amount]
            for coin in completed_targets:
                self.logger.info(f"Mining target reached for {coin.symbol}: {coin.current_amount:.2f}/{coin.target_amount:.2f}")
                
                # In a real implementation, we might move this to a 'completed' list
                # For now, we'll just keep it in the targets but with lower priority
                coin.priority = 0.1
            
            # Re-prioritize targets based on updated data
            await self._prioritize_target_coins()
            
            # Log current targets
            self.logger.info(f"Current mining targets: {len(self.target_coins)} coins")
            return True
            
        except Exception as e:
            self.logger.error(f"Error evaluating mining targets: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def _trade_underperforming_assets(self):
        """
        Trade underperforming mining assets for better opportunities.
        
        This method identifies underperforming assets in the mining portfolio
        and attempts to trade them for more promising opportunities.
        
        Returns:
            bool: True if trading was successful, False otherwise
        """
        try:
            self.logger.debug("Evaluating underperforming assets for trading")
            
            # Skip if trading is disabled or if trading component is unavailable
            if not self.auto_trade_underperforming:
                return True
                
            if not hasattr(self, "trading_intelligence") or not self.trading_intelligence:
                self.logger.warning("Cannot trade assets: Trading Intelligence component not available")
                return False
                
            # Find underperforming assets (bottom 10% by profitability)
            if len(self.target_coins) <= 1:
                return True  # Need at least 2 coins to identify underperformers
                
            # Sort by profitability (ascending)
            sorted_coins = sorted(self.target_coins, key=lambda x: x.profitability_score)
            underperformers = sorted_coins[:max(1, len(sorted_coins) // 10)]  # Bottom 10%
            
            # Attempt to trade each underperformer
            for coin in underperformers:
                # Skip if we haven't mined much of this coin yet
                if coin.current_amount < 10.0:
                    continue
                    
                self.logger.info(f"Attempting to trade underperforming asset: {coin.symbol}")
                
                # In a real implementation, this would call the trading component
                if hasattr(self.trading_intelligence, "trade_asset"):
                    result = await self.trading_intelligence.trade_asset(
                        asset=coin.symbol,
                        amount=coin.current_amount * 0.5,  # Trade half
                        reason="underperforming"
                    )
                    
                    if result and result.get("success", False):
                        self.logger.info(f"Successfully traded {result.get('amount_sold')} {coin.symbol} "
                                        f"for {result.get('amount_bought')} {result.get('bought_asset')}")
                        
                        # Update the coin's current amount
                        coin.current_amount -= result.get('amount_sold', 0)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error trading underperforming assets: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def _update_mining_strategies(self):
        """
        Update mining strategies based on market conditions and profitability metrics.
        
        This method adjusts the mining strategy for each coin based on
        current market conditions, difficulty trends, and profitability.
        
        Returns:
            bool: True if strategies were updated successfully, False otherwise
        """
        try:
            self.logger.debug("Updating mining strategies")
            
            # Skip if no target coins
            if not self.target_coins:
                return True
                
            # Update profitability scores first
            await self._update_coin_profitability_scores()
            
            # Count coins by algorithm
            algorithm_counts = {}
            for coin in self.target_coins:
                algorithm = coin.algorithm.value if hasattr(coin.algorithm, "value") else str(coin.algorithm)
                if algorithm not in algorithm_counts:
                    algorithm_counts[algorithm] = 0
                algorithm_counts[algorithm] += 1
            
            # Adjust priorities based on market conditions and diversity
            strategy_adjustments = 0
            for coin in self.target_coins:
                algorithm = coin.algorithm.value if hasattr(coin.algorithm, "value") else str(coin.algorithm)
                coin_data = self.coin_data.get(coin.symbol, {})
                
                # Skip if we don't have enough data
                if not coin_data:
                    continue
                    
                # Check for difficulty trend
                difficulty_trend = coin_data.get("difficulty_trend", 0.0)
                price_trend = coin_data.get("price_trend", 0.0)
                
                # Calculate a strategy adjustment factor
                # Positive for favorable conditions, negative for unfavorable
                strategy_factor = 0.0
                
                # Difficulty decreasing is good
                if difficulty_trend < -0.1:  # Decreasing difficulty
                    strategy_factor += 0.2
                    self.logger.info(f"Favorable difficulty trend for {coin.symbol}: {difficulty_trend:.2f}")
                    
                # Difficulty increasing rapidly is bad
                elif difficulty_trend > 0.2:  # Rapidly increasing difficulty
                    strategy_factor -= 0.3
                    self.logger.info(f"Unfavorable difficulty trend for {coin.symbol}: {difficulty_trend:.2f}")
                
                # Price trend impact
                if price_trend > 0.05:  # Price increasing
                    strategy_factor += 0.2
                elif price_trend < -0.1:  # Price decreasing significantly
                    strategy_factor -= 0.2
                
                # Adjust for algorithm diversity (avoid concentration)
                if algorithm_counts.get(algorithm, 0) > 3:  # Too many coins with same algorithm
                    strategy_factor -= 0.1
                
                # Apply adjustment to priority if significant
                if abs(strategy_factor) > 0.1:
                    old_priority = coin.priority
                    # Adjust priority but keep within reasonable bounds
                    coin.priority = max(0.1, min(2.0, coin.priority * (1.0 + strategy_factor)))
                    
                    if abs(coin.priority - old_priority) > 0.1:
                        self.logger.info(f"Adjusted mining priority for {coin.symbol}: {old_priority:.2f} -> {coin.priority:.2f}")
                        strategy_adjustments += 1
            
            # Re-prioritize after adjustments
            if strategy_adjustments > 0:
                await self._prioritize_target_coins()
                
            self.logger.info(f"Mining strategies updated with {strategy_adjustments} adjustments")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating mining strategies: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _collect_mining_rewards(self):
        """
        Collect pending mining rewards from various pools.
        
        This method checks for and collects any pending mining rewards
        across different pools and currencies.
        
        Returns:
            bool: True if collection was successful, False otherwise
        """
        try:
            self.logger.debug("Collecting mining rewards")
            
            # Skip if auto-collect is disabled
            if not self.auto_collect_rewards:
                return True
                
            # Skip if wallet manager is not available
            if not self.wallet_manager:
                self.logger.warning("Cannot collect rewards: Wallet Manager not available")
                return False
                
            # Check each coin for uncollected rewards
            total_collected = 0.0
            total_value_collected = 0.0
            
            for coin_symbol, rewards in self.mining_rewards_by_coin.items():
                # Filter for uncollected rewards
                uncollected = [r for r in rewards if not r.get("collected", False)]
                
                if not uncollected:
                    continue
                    
                # Calculate total uncollected amount
                uncollected_amount = sum(r["amount"] for r in uncollected)
                
                # Only collect once we have at least 10 coins for this asset
                if uncollected_amount < 10.0:
                    continue
                    
                # Get price data if available
                price = 0.0
                if coin_symbol in self.coin_data:
                    price = self.coin_data[coin_symbol].get("price", 0.0)
                
                # Group by pool for more efficient collection
                by_pool = {}
                for reward in uncollected:
                    pool = reward.get("pool", "unknown")
                    if pool not in by_pool:
                        by_pool[pool] = 0.0
                    by_pool[pool] += reward["amount"]
                
                # Collect from each pool
                for pool, amount in by_pool.items():
                    self.logger.info(f"Collecting {amount:.2f} {coin_symbol} from pool: {pool}")
                    
                    # In a real implementation, this would call the wallet manager
                    # For now, we'll simulate the collection process
                    try:
                        if hasattr(self.wallet_manager, "collect_mining_rewards"):
                            result = await self.wallet_manager.collect_mining_rewards(
                                coin=coin_symbol,
                                pool=pool,
                                amount=amount
                            )
                            
                            if result and result.get("success", False):
                                # Mark rewards as collected
                                for reward in uncollected:
                                    if reward.get("pool") == pool:
                                        reward["collected"] = True
                                        
                                actual_amount = result.get("collected_amount", amount)
                                total_collected += 1
                                total_value_collected += actual_amount * price
                                
                                self.logger.info(f"Successfully collected {actual_amount:.2f} {coin_symbol} worth ${actual_amount * price:.2f}")
                            else:
                                self.logger.warning(f"Failed to collect rewards for {coin_symbol} from {pool}: {result.get('error', 'Unknown error')}")
                        else:
                            self.logger.warning("Wallet manager does not support reward collection")
                            
                    except Exception as e:
                        self.logger.error(f"Error collecting rewards for {coin_symbol} from {pool}: {e}")
                        # Continue with other pools despite error
            
            if total_collected > 0:
                self.logger.info(f"Total rewards collected: {total_collected} coins worth ${total_value_collected:.2f}")
            else:
                self.logger.info("No rewards collected in this cycle")
                
            return True
                
        except Exception as e:
            self.logger.error(f"Error collecting mining rewards: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def _discover_new_mining_opportunities(self):
        """
        Discover new mining opportunities to add to the target list.
        
        This method searches for new coins or tokens that might be profitable
        to add to the mining target list based on market data and trends.
        
        Returns:
            bool: True if discovery was successful, False otherwise
        """
        try:
            self.logger.debug("Discovering new mining opportunities")
            
            # In a real implementation, this would scan market data
            # and blockchain networks for new opportunities
            if self.market_data_provider and hasattr(self.market_data_provider, "get_emerging_opportunities"):
                try:
                    opportunities = await self.market_data_provider.get_emerging_opportunities(limit=5)
                    
                    for opportunity in opportunities:
                        # Check if we're already targeting this coin
                        if opportunity["symbol"] in [coin.symbol for coin in self.target_coins]:
                            continue
                            
                        # Add new opportunity to target list
                        try:
                            algorithm = MiningAlgorithm(opportunity.get("algorithm", "sha256"))
                        except ValueError:
                            algorithm = MiningAlgorithm.SHA256  # Default to SHA256 if not recognized
                            
                        new_coin = CoinTarget(
                            symbol=opportunity["symbol"],
                            name=opportunity.get("name", opportunity["symbol"]),
                            algorithm=algorithm,
                            target_amount=opportunity.get("target_amount", 1000.0),
                            current_amount=0.0,
                            priority=1.0,
                            daily_emission=opportunity.get("daily_emission", 0.0)
                        )
                        
                        # Calculate initial profitability
                        new_coin.profitability_score = float(await self._calculate_initial_profitability(opportunity))
                        
                        # Add to target list
                        self.target_coins.append(new_coin)
                        self.logger.info(f"Added new mining target: {new_coin.symbol} with initial score {new_coin.profitability_score:.2f}")
                        
                except Exception as e:
                    self.logger.warning(f"Error getting emerging opportunities: {e}")
            
            # Re-prioritize with new targets included
            if self.target_coins:
                await self._prioritize_target_coins()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error discovering new mining opportunities: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def _update_coin_profitability_scores(self):
        """
        Update profitability scores for all target coins.
        
        This method recalculates profitability scores for all target coins based on
        current market data, difficulty, and other factors.
        
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            self.logger.debug("Updating coin profitability scores")
            
            for coin in self.target_coins:
                coin_data = self.coin_data.get(coin.symbol, {})
                if not coin_data:
                    continue
                    
                # Base profitability factors
                price = coin_data.get("price", 0.0)
                volume = coin_data.get("daily_volume", 0.0)
                market_cap = coin_data.get("market_cap", 0.0)
                difficulty = coin_data.get("difficulty", 1.0)
                difficulty_trend = coin_data.get("difficulty_trend", 0.0)
                
                # Calculate profitability score using weighted factors
                # Higher price and volume increase score
                # Higher difficulty decreases score
                # Rising difficulty (positive trend) decreases score
                
                price_factor = price * self.algorithm_weights.get("price", 0.3)
                volume_factor = min(1.0, volume / 1000000) * self.algorithm_weights.get("volume", 0.1)
                difficulty_factor = (1.0 / max(1.0, difficulty)) * self.algorithm_weights.get("difficulty", 0.3)
                trend_factor = (1.0 - min(1.0, max(-1.0, difficulty_trend))) * self.algorithm_weights.get("difficulty_trend", 0.2)
                
                # Calculate final score
                profitability_score = (price_factor + volume_factor + difficulty_factor + trend_factor) * 100.0
                
                # Update coin target with new score
                coin.profitability_score = float(profitability_score)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating coin profitability scores: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def _prioritize_target_coins(self):
        """
        Prioritize target coins based on profitability, target completion, and market conditions.
        
        This method calculates a comprehensive priority score for each target coin based on:
        1. Profitability scores from market analysis
        2. Current mining progress towards target amount
        3. Time elapsed since last mining activity
        4. Market momentum and sentiment data
        5. Network difficulty trends
        6. Current portfolio balance and diversification needs
        7. Social and community factors (development activity, community growth)
        
        Returns:
            bool: True if prioritization was successful, False otherwise
        """
        try:
            self.logger.info("Prioritizing target coins for mining using advanced algorithms")
            
            # Skip if no target coins
            if not self.target_coins:
                self.logger.warning("No target coins to prioritize")
                return True
                
            # Update all profitability scores first
            await self._update_coin_profitability_scores()
            
            # Get portfolio data for balance considerations
            portfolio_data = {}
            for coin in self.target_coins:
                if coin.current_amount > 0:
                    # Use coin prices from coin_data if available
                    price = 0.0
                    if coin.symbol in self.coin_data:
                        price = self.coin_data[coin.symbol].get("price", 0.0)
                    portfolio_data[coin.symbol] = coin.current_amount * price
            
            total_portfolio_value = sum(portfolio_data.values())
            
            # Calculate additional metrics for each coin
            coin_metrics = {}
            for coin in self.target_coins:
                symbol = coin.symbol
                
                # Calculate basic progress metrics
                progress = min(1.0, coin.current_amount / coin.target_amount) if coin.target_amount > 0 else 0
                progress_urgency = 1.0 - progress  # Higher urgency when less progress
                
                # Calculate time-based urgency with non-linear scaling
                time_urgency = 0.0
                if coin.last_mined:
                    # Progressive urgency scale - grows faster after longer periods
                    days_since_mined = (datetime.now() - coin.last_mined).total_seconds() / 86400
                    time_urgency = min(1.0, (days_since_mined / 5.0) ** 1.5)  # Non-linear growth, max after 5 days
                else:
                    time_urgency = 0.9  # Never mined = high urgency, but not maximum
                
                # Market momentum factor (rising markets get priority)
                momentum_factor = 0.5  # Neutral default
                if symbol in self.coin_data:
                    # Scale from -1.0 (strong downtrend) to 1.0 (strong uptrend)
                    momentum = self.coin_data[symbol].get("price_trend", 0.0)
                    momentum_factor = (momentum + 1) / 2  # Rescale to 0-1
                
                # Network difficulty trend factor (decreasing difficulty is better)
                difficulty_factor = 0.5  # Neutral default
                if symbol in self.coin_data:
                    difficulty_trend = self.coin_data[symbol].get("difficulty_trend", 0.0)
                    if difficulty_trend < 0:  # Decreasing difficulty
                        difficulty_factor = 0.7 + min(0.3, abs(difficulty_trend))  # 0.7-1.0 for decreasing difficulty
                    else:  # Increasing difficulty
                        difficulty_factor = max(0.1, 0.7 - min(0.6, difficulty_trend))  # 0.1-0.7 for increasing difficulty
                
                # Portfolio balance factor (underrepresented coins get higher priority)
                balance_factor = 0.5  # Neutral default
                if total_portfolio_value > 0 and symbol in portfolio_data and portfolio_data[symbol] > 0:
                    coin_percentage = portfolio_data[symbol] / total_portfolio_value
                    target_percentage = 1.0 / len(self.target_coins)  # Equal distribution as default target
                    
                    # If we're under target percentage, increase priority
                    if coin_percentage < target_percentage:
                        # How far below target (0-1 scale)
                        shortfall = 1.0 - (coin_percentage / target_percentage)
                        balance_factor = 0.5 + (shortfall * 0.4)  # 0.5-0.9 based on shortfall
                    else:
                        # How far above target (0-1 scale)
                        excess = min(1.0, (coin_percentage / target_percentage) - 1.0)
                        balance_factor = max(0.2, 0.5 - (excess * 0.3))  # 0.2-0.5 based on excess
                
                # Social/community factor from coin data if available
                social_factor = 0.5  # Neutral default
                if symbol in self.coin_data:
                    social_factor = self.coin_data[symbol].get("social_score", 0.5)
                
                # Store all metrics for this coin
                coin_metrics[symbol] = {
                    'progress_urgency': progress_urgency,
                    'time_urgency': time_urgency,
                    'momentum_factor': momentum_factor,
                    'difficulty_factor': difficulty_factor,
                    'balance_factor': balance_factor,
                    'social_factor': social_factor
                }
                
                # Log detailed metrics for debugging
                self.logger.debug(f"Metrics for {symbol}: Progress: {progress_urgency:.2f}, Time: {time_urgency:.2f}, "
                                f"Momentum: {momentum_factor:.2f}, Difficulty: {difficulty_factor:.2f}, "
                                f"Balance: {balance_factor:.2f}, Social: {social_factor:.2f}")
            
            # Apply weighting factors to calculate final urgency scores
            for coin in self.target_coins:
                metrics = coin_metrics.get(coin.symbol, {})
                if not metrics:
                    coin.urgency_score = 0.5  # Default if metrics unavailable
                    continue
                    
                # Weighted combination of factors
                weights = {
                    'progress_urgency': 0.30,  # High weight for progress towards target
                    'time_urgency': 0.20,      # Moderate weight for time since last mined
                    'momentum_factor': 0.20,   # Substantial weight for market momentum
                    'difficulty_factor': 0.15, # Moderate weight for difficulty trends
                    'balance_factor': 0.10,    # Lower weight for portfolio balance
                    'social_factor': 0.05      # Lower weight for social/community factors
                }
                
                # Calculate final urgency score
                coin.urgency_score = sum(metrics.get(factor, 0.5) * weight 
                                       for factor, weight in weights.items())
                
                # Enforce bounds
                coin.urgency_score = max(0.1, min(1.0, coin.urgency_score))
            
            # Determine market condition to adjust weighting between profitability and urgency
            # In bear markets, emphasize profitability more; in bull markets, balance both
            market_condition = 0.0  # Neutral default
            
            # Check if we have market trend data in coin_data
            market_trends = []
            for symbol, data in self.coin_data.items():
                if 'price_trend' in data:
                    market_trends.append(data['price_trend'])
            
            # Calculate overall market condition if we have trend data
            if market_trends:
                # Average of all price trends (-1.0 to 1.0 scale)
                market_condition = sum(market_trends) / len(market_trends)
            
            profitability_weight = 0.7 - (market_condition * 0.2)  # 0.5 in bull, 0.9 in bear
            urgency_weight = 1.0 - profitability_weight
            
            # Sort coins by combined score with dynamic weighting
            self.target_coins.sort(
                key=lambda c: (c.profitability_score * profitability_weight + 
                              c.urgency_score * urgency_weight) * c.priority, 
                reverse=True
            )
            
            # Log top coins
            self.logger.info(f"Top mining targets after prioritization (Prof weight: {profitability_weight:.2f}, Urg weight: {urgency_weight:.2f}):")
            for i, coin in enumerate(self.target_coins[:5], 1):
                combined_score = (coin.profitability_score * profitability_weight + 
                                 coin.urgency_score * urgency_weight) * coin.priority
                self.logger.info(f"{i}. {coin.symbol}: Profit {coin.profitability_score:.2f}, "
                               f"Urgency {coin.urgency_score:.2f}, Priority {coin.priority:.2f}, "
                               f"Combined {combined_score:.2f}")
            
            # Publish prioritized coins list to event bus for other components
            if self.event_bus:
                await self.event_bus.publish("mining.target_coins_prioritized", {
                    "prioritized_coins": [
                        {
                            "symbol": coin.symbol,
                            "algorithm": coin.algorithm.value if hasattr(coin.algorithm, "value") else str(coin.algorithm),
                            "profitability_score": coin.profitability_score,
                            "urgency_score": coin.urgency_score,
                            "priority": coin.priority,
                            "target_amount": coin.target_amount,
                            "current_amount": coin.current_amount,
                            "last_mined": coin.last_mined.isoformat() if coin.last_mined else None
                        }
                        for coin in self.target_coins[:10]  # Send top 10 coins
                    ],
                    "timestamp": datetime.now().isoformat(),
                    "market_condition": market_condition
                })
                
            return True
                
        except Exception as e:
            self.logger.error(f"Error prioritizing target coins: {e}")
            self.logger.error(traceback.format_exc())
            return False

    async def _optimize_parallel_mining_distribution(self):
        """
        Optimize the distribution of mining resources across multiple coins.
        
        This method calculates the optimal distribution of mining resources
        (hashpower, GPUs, etc.) across different target coins based on their
        profitability scores and other factors.
        
        Returns:
            bool: True if distribution was optimized successfully, False otherwise
        """
        try:
            self.logger.debug("Optimizing parallel mining distribution")
            
            # Skip if parallel mining is not active
            if not self.parallel_mining_active:
                return True
                
            # Need at least 2 coins to distribute resources
            if len(self.target_coins) < 2:
                return True
                
            # Update profitability scores first
            await self._update_coin_profitability_scores()
            
            # Prioritize coins
            await self._prioritize_target_coins()
            
            # Calculate distribution based on scores
            total_score = sum(coin.profitability_score * coin.priority for coin in self.target_coins)
            if total_score <= 0:
                self.logger.warning("Cannot optimize distribution: all coins have zero profitability")
                return False
                
            # Calculate percentage allocation for each coin
            allocations = []
            for coin in self.target_coins:
                score = coin.profitability_score * coin.priority
                percentage = (score / total_score) * 100 if total_score > 0 else 0
                allocations.append({
                    "symbol": coin.symbol,
                    "algorithm": coin.algorithm.value if hasattr(coin.algorithm, "value") else str(coin.algorithm),
                    "percentage": percentage,
                    "score": score
                })
                
            # Sort by percentage (descending)
            allocations.sort(key=lambda x: x["percentage"], reverse=True)
            
            # Log distribution
            self.logger.info("Recommended mining distribution:")
            for alloc in allocations[:5]:  # Top 5
                self.logger.info(f"{alloc['symbol']}: {alloc['percentage']:.1f}%")
                
            # Publish distribution recommendation to mining system
            if self.event_bus:
                await self.event_bus.publish("mining.distribution_recommendation", {
                    "allocations": allocations,
                    "timestamp": datetime.now().isoformat(),
                    "source": "mining_intelligence"
                })
                
            return True
                
        except Exception as e:
            self.logger.error(f"Error optimizing mining distribution: {e}")
            self.logger.error(traceback.format_exc())
            return False
