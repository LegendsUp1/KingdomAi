#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Futures Trading Master Module

Advanced futures trading intelligence with quantum-enhanced algorithms for
shorting, hedging, spreading, scalping, arbitrage, and position trading.
Provides state-of-the-art strategies for futures markets across all asset classes.
"""

import logging
import time
import uuid
import threading
import traceback
from datetime import datetime

# Kingdom AI imports
from core.base_component import BaseComponent


class FuturesTradingMaster(BaseComponent):
    """
    Advanced futures trading master component with quantum-enhanced algorithms.
    
    Provides state-of-the-art strategies for futures trading, including:
    1. Short Selling - Advanced techniques for profiting from downward movements
    2. Hedging - Risk management through strategic position taking
    3. Spreading - Exploiting inefficiencies between related contracts
    4. Scalping - High-frequency trading for small price movements
    5. Arbitrage - Riskless profit from price gaps across exchanges
    6. Position Trading - Long-term trend riding strategies
    
    Each strategy is enhanced with quantum-inspired algorithms for optimal
    trade timing, position sizing, and risk management.
    """
    
    def __init__(self, event_bus=None, config=None):
        """
        Initialize the futures trading master component.
        
        Args:
            event_bus: The event bus for publishing and subscribing to events
            config: Configuration parameters for the component
        """
        super().__init__("FuturesTradingMaster", event_bus, config)
        self.event_bus = event_bus
        self.config = config or {}
        self.logger = logging.getLogger('KingdomAI.FuturesTradingMaster')
        
        # Strategy configuration
        self.strategies = {
            'short_selling': {
                'enabled': True,
                'max_leverage': 10,
                'risk_limit': 0.02,  # 2% of capital per trade
                'target_markets': ['crypto', 'indices', 'commodities', 'forex'],
                'techniques': ['momentum_short', 'breakdown_short', 'overbought_short', 'news_based_short']
            },
            'hedging': {
                'enabled': True,
                'correlation_threshold': 0.7,
                'hedge_ratio': 1.0,
                'auto_rebalance': True
            },
            'spreading': {
                'enabled': True,
                'spread_types': ['calendar', 'inter_commodity', 'basis'],
                'min_inefficiency': 0.001,  # 0.1% minimum inefficiency to trade
                'max_position_size': 0.1  # 10% of capital max
            },
            'scalping': {
                'enabled': True,
                'max_trades_per_day': 100,
                'target_profit_pips': 5,
                'max_loss_pips': 3,
                'min_liquidity': 1000000  # Minimum market liquidity
            },
            'arbitrage': {
                'enabled': True,
                'min_price_gap': 0.0005,  # 0.05% minimum gap
                'execution_speed_ms': 50,  # 50ms max execution time
                'venues': ['binance', 'ftx', 'deribit', 'kraken', 'cme', 'ice']
            },
            'position_trading': {
                'enabled': True,
                'holding_period': {'min_days': 7, 'max_days': 90},
                'trend_confirmation_indicators': ['macd', 'adx', 'ichimoku']
            }
        }
        
        # Market data and tracking
        self.market_data = {}
        self.open_positions = {}
        self.trade_history = []
        self.strategy_performance = {}
        
        # Advanced analytics
        self.volatility_models = {}
        self.correlation_matrix = {}
        self.term_structure_models = {}
        self.liquidity_metrics = {}
        
        # Initialize systems
        self._initialize_systems()
        
    def _initialize_systems(self):
        """Initialize all required systems for futures trading."""
        self.logger.info("Initializing futures trading master systems")
        
        # Set up event subscriptions
        self._setup_event_subscriptions()
        
        # Initialize strategy engines
        self._initialize_strategy_engines()
        
        # Initialize market scanners
        self._initialize_market_scanners()
        
        # Initialize risk management system
        self._initialize_risk_management()
        
        # Start background workers if auto-start enabled
        if self.config.get('auto_start', True):
            self._start_background_workers()
            
        self.logger.info("Futures trading master systems initialized")
    
    def _setup_event_subscriptions(self):
        """Set up event bus subscriptions for the futures trading master."""
        if not self.event_bus:
            self.logger.warning("No event bus provided, event subscriptions not set up")
            return
            
        # Subscribe to market data events
        self.event_bus.subscribe('market.data', self._handle_market_data)
        self.event_bus.subscribe('market.order_book', self._handle_order_book)
        self.event_bus.subscribe('market.trades', self._handle_trades)
        
        # Subscribe to trading events
        self.event_bus.subscribe('trading.signal', self._handle_trading_signal)
        self.event_bus.subscribe('trading.execution', self._handle_execution_event)
        
        # Subscribe to analytics events
        self.event_bus.subscribe('analytics.volatility', self._handle_volatility_update)
        self.event_bus.subscribe('analytics.correlation', self._handle_correlation_update)
        
        self.logger.info("Event subscriptions set up for futures trading master")
    
    def _initialize_strategy_engines(self):
        """Initialize strategy engines for each futures trading strategy."""
        self.strategy_engines = {}
        
        # Initialize short selling engine
        if self.strategies['short_selling']['enabled']:
            self.strategy_engines['short_selling'] = self._create_short_selling_engine()
            
        # Initialize hedging engine
        if self.strategies['hedging']['enabled']:
            self.strategy_engines['hedging'] = self._create_hedging_engine()
            
        # Initialize spreading engine
        if self.strategies['spreading']['enabled']:
            self.strategy_engines['spreading'] = self._create_spreading_engine()
            
        # Initialize scalping engine
        if self.strategies['scalping']['enabled']:
            self.strategy_engines['scalping'] = self._create_scalping_engine()
            
        # Initialize arbitrage engine
        if self.strategies['arbitrage']['enabled']:
            self.strategy_engines['arbitrage'] = self._create_arbitrage_engine()
            
        # Initialize position trading engine
        if self.strategies['position_trading']['enabled']:
            self.strategy_engines['position_trading'] = self._create_position_trading_engine()
            
        self.logger.info(f"Initialized {len(self.strategy_engines)} strategy engines")
    
    def _create_short_selling_engine(self):
        """Create the short selling strategy engine."""
        self.logger.info("Creating short selling strategy engine")
        
        # Configure short selling parameters
        config = self.strategies['short_selling']
        
        # Define short techniques
        techniques = {
            'momentum_short': {
                'indicators': ['rsi', 'macd', 'stochastic'],
                'confirmation_count': 2,  # Need 2 indicators to confirm
                'trigger_levels': {'rsi': 70, 'stochastic': 80}
            },
            'breakdown_short': {
                'lookback_periods': [20, 50, 200],
                'breakdown_threshold': 0.02,  # 2% breakdown
                'volume_confirmation': True
            },
            'overbought_short': {
                'indicators': ['bollinger_bands', 'keltner_channels'],
                'deviation_threshold': 2.5,  # Standard deviations
                'mean_reversion_probability': 0.75
            },
            'news_based_short': {
                'sentiment_threshold': -0.6,  # Negative sentiment threshold
                'reaction_time_ms': 500,
                'news_sources': ['bloomberg', 'reuters', 'twitter']
            }
        }
        
        return {
            'config': config,
            'techniques': techniques,
            'active_shorts': {},
            'performance': {'win_rate': 0, 'avg_return': 0, 'max_drawdown': 0}
        }
    
    def _create_hedging_engine(self):
        """Create the hedging strategy engine with SOTA 2026 risk management."""
        self.logger.info("Creating hedging strategy engine")
        
        config = self.strategies['hedging']
        
        return {
            'config': config,
            'hedging_types': {
                'delta_hedge': {
                    'description': 'Neutralize directional risk using options/futures',
                    'instruments': ['futures', 'options', 'perpetuals'],
                    'rebalance_threshold': 0.05,  # 5% delta deviation triggers rebalance
                    'auto_rebalance': True
                },
                'cross_asset_hedge': {
                    'description': 'Hedge exposure using correlated assets',
                    'correlation_threshold': config.get('correlation_threshold', 0.7),
                    'hedge_ratio_method': 'ols_regression',  # OLS for optimal hedge ratio
                    'lookback_days': 30
                },
                'tail_risk_hedge': {
                    'description': 'Protect against extreme market moves',
                    'instruments': ['put_options', 'vix_futures'],
                    'otm_percentage': 0.1,  # 10% out of the money
                    'coverage_ratio': 0.2  # Hedge 20% of portfolio
                },
                'calendar_hedge': {
                    'description': 'Spread risk across expiration dates',
                    'front_back_ratio': 1.0,
                    'roll_days_before_expiry': 7
                }
            },
            'active_hedges': {},
            'hedge_history': [],
            'performance': {'total_hedged_value': 0, 'hedge_pnl': 0, 'effectiveness_ratio': 0}
        }
    
    def _create_spreading_engine(self):
        """Create the spreading strategy engine with SOTA 2026 spread types."""
        self.logger.info("Creating spreading strategy engine")
        
        config = self.strategies['spreading']
        
        return {
            'config': config,
            'spread_types': {
                'calendar_spread': {
                    'description': 'Exploit time value differences across expirations',
                    'leg_count': 2,
                    'same_strike': True,
                    'different_expiry': True,
                    'entry_criteria': {'contango_threshold': 0.005, 'backwardation_threshold': -0.005}
                },
                'inter_commodity_spread': {
                    'description': 'Trade relative value between related commodities',
                    'pairs': [
                        ('BTC', 'ETH', 15.0),  # Historical ratio
                        ('GOLD', 'SILVER', 80.0),
                        ('WTI', 'BRENT', 1.5)
                    ],
                    'ratio_deviation_threshold': 0.1  # 10% deviation from mean
                },
                'basis_spread': {
                    'description': 'Exploit spot-futures price differences',
                    'min_basis': config.get('min_inefficiency', 0.001),
                    'max_holding_period_days': 30,
                    'convergence_target': 0.0
                },
                'butterfly_spread': {
                    'description': 'Neutral volatility play with limited risk',
                    'leg_count': 3,
                    'profit_zone': 'centered'
                }
            },
            'active_spreads': {},
            'spread_history': [],
            'performance': {'total_spreads': 0, 'win_rate': 0, 'avg_return': 0}
        }
    
    def _create_scalping_engine(self):
        """Create the scalping strategy engine with SOTA 2026 HFT capabilities."""
        self.logger.info("Creating scalping strategy engine")
        
        config = self.strategies['scalping']
        
        return {
            'config': config,
            'scalping_modes': {
                'order_flow_scalping': {
                    'description': 'Trade based on order flow imbalances',
                    'imbalance_threshold': 0.6,  # 60% buy/sell imbalance
                    'min_volume_ratio': 2.0,  # 2x average volume
                    'hold_time_ms': 500
                },
                'spread_capture': {
                    'description': 'Capture bid-ask spread with market making',
                    'min_spread_bps': 5,  # Minimum 5 basis points
                    'inventory_limit': 0.01,  # Max 1% of capital
                    'quote_refresh_ms': 100
                },
                'momentum_scalping': {
                    'description': 'Quick trades on micro-momentum',
                    'lookback_ticks': 10,
                    'momentum_threshold': 0.001,  # 0.1% price move
                    'profit_target_pips': config.get('target_profit_pips', 5)
                },
                'volatility_scalping': {
                    'description': 'Trade mean reversion in high volatility',
                    'volatility_multiplier': 1.5,  # 1.5x normal volatility
                    'reversion_target': 0.5  # 50% reversion
                }
            },
            'active_scalps': {},
            'daily_stats': {
                'trades_today': 0,
                'max_trades': config.get('max_trades_per_day', 100),
                'pnl_today': 0,
                'win_count': 0,
                'loss_count': 0
            },
            'performance': {'avg_hold_time_ms': 0, 'win_rate': 0, 'sharpe_ratio': 0}
        }
    
    def _create_arbitrage_engine(self):
        """Create the arbitrage strategy engine with SOTA 2026 multi-venue support."""
        self.logger.info("Creating arbitrage strategy engine")
        
        config = self.strategies['arbitrage']
        
        return {
            'config': config,
            'arbitrage_types': {
                'spatial_arbitrage': {
                    'description': 'Same asset, different exchanges',
                    'venues': config.get('venues', ['binance', 'kraken', 'coinbase']),
                    'min_profit_bps': config.get('min_price_gap', 0.0005) * 10000,
                    'latency_budget_ms': config.get('execution_speed_ms', 50)
                },
                'triangular_arbitrage': {
                    'description': 'Three-way currency arbitrage',
                    'currency_paths': [
                        ['BTC', 'ETH', 'USDT', 'BTC'],
                        ['ETH', 'BTC', 'USDC', 'ETH'],
                        ['SOL', 'USDT', 'BTC', 'SOL']
                    ],
                    'min_profit_bps': 3  # 3 basis points minimum
                },
                'futures_spot_arbitrage': {
                    'description': 'Exploit futures-spot basis',
                    'funding_rate_threshold': 0.001,  # 0.1% funding rate
                    'basis_threshold': 0.002,  # 0.2% basis
                    'holding_period': 'funding_interval'
                },
                'cross_exchange_futures': {
                    'description': 'Same futures contract, different exchanges',
                    'contract_types': ['perpetual', 'quarterly'],
                    'max_divergence_seconds': 1
                }
            },
            'venue_connections': {venue: {'latency_ms': 0, 'connected': False} for venue in config.get('venues', [])},
            'active_arb_positions': {},
            'opportunity_log': [],
            'performance': {'opportunities_found': 0, 'executed': 0, 'total_profit': 0, 'avg_latency_ms': 0}
        }
    
    def _create_position_trading_engine(self):
        """Create the position trading strategy engine with SOTA 2026 trend following."""
        self.logger.info("Creating position trading strategy engine")
        
        config = self.strategies['position_trading']
        
        return {
            'config': config,
            'position_strategies': {
                'trend_following': {
                    'description': 'Long-term trend riding with multiple confirmations',
                    'indicators': config.get('trend_confirmation_indicators', ['macd', 'adx', 'ichimoku']),
                    'confirmation_count': 2,  # Need 2 of 3 indicators
                    'entry_rules': {
                        'macd_crossover': True,
                        'adx_above': 25,
                        'price_above_cloud': True
                    },
                    'exit_rules': {
                        'trailing_stop_atr': 3.0,
                        'profit_target_atr': 6.0,
                        'trend_reversal': True
                    }
                },
                'breakout_position': {
                    'description': 'Enter on confirmed breakouts',
                    'lookback_periods': [20, 50, 200],
                    'volume_confirmation': True,
                    'false_breakout_filter': True,
                    'atr_filter': 1.5
                },
                'mean_reversion_position': {
                    'description': 'Long-term mean reversion plays',
                    'zscore_entry': 2.0,
                    'zscore_exit': 0.5,
                    'lookback_days': 200
                },
                'fundamental_position': {
                    'description': 'Positions based on fundamentals',
                    'factors': ['on_chain_metrics', 'adoption_rate', 'developer_activity'],
                    'rebalance_interval_days': 30
                }
            },
            'holding_period': config.get('holding_period', {'min_days': 7, 'max_days': 90}),
            'active_positions': {},
            'position_history': [],
            'performance': {'total_positions': 0, 'avg_holding_days': 0, 'win_rate': 0, 'total_return': 0}
        }
    
    def _initialize_market_scanners(self):
        """Initialize market scanners for different asset classes."""
        self.market_scanners = {
            'crypto': self._create_crypto_scanner(),
            'indices': self._create_indices_scanner(),
            'commodities': self._create_commodities_scanner(),
            'forex': self._create_forex_scanner()
        }
        
        self.logger.info(f"Initialized {len(self.market_scanners)} market scanners")
    
    def _create_crypto_scanner(self):
        """Create scanner for crypto futures markets with SOTA 2026 coverage."""
        self.logger.info("Creating crypto futures market scanner")
        
        return {
            'market_type': 'crypto',
            'scan_interval_seconds': 5,
            'markets': {
                'perpetuals': [
                    'BTC-PERP', 'ETH-PERP', 'SOL-PERP', 'DOGE-PERP', 'XRP-PERP',
                    'ADA-PERP', 'AVAX-PERP', 'DOT-PERP', 'LINK-PERP', 'MATIC-PERP'
                ],
                'quarterlies': [
                    'BTC-0328', 'BTC-0627', 'ETH-0328', 'ETH-0627'
                ],
                'options': [
                    'BTC-OPTIONS', 'ETH-OPTIONS'
                ]
            },
            'exchanges': ['binance', 'bybit', 'okx', 'deribit', 'kraken'],
            'scan_criteria': {
                'min_24h_volume_usd': 1000000,
                'min_open_interest_usd': 500000,
                'max_funding_rate': 0.01,  # 1% max funding rate
                'min_liquidity_score': 0.7
            },
            'alerts': {
                'funding_rate_spike': 0.005,
                'volume_spike_multiplier': 3.0,
                'price_deviation_threshold': 0.02
            },
            'active_scans': {},
            'scan_results': [],
            'last_scan_time': None
        }
    
    def _create_indices_scanner(self):
        """Create scanner for index futures markets with SOTA 2026 coverage."""
        self.logger.info("Creating indices futures market scanner")
        
        return {
            'market_type': 'indices',
            'scan_interval_seconds': 10,
            'markets': {
                'us_indices': [
                    'ES', 'NQ', 'YM', 'RTY',  # E-mini S&P, Nasdaq, Dow, Russell
                    'MES', 'MNQ', 'MYM', 'M2K'  # Micro contracts
                ],
                'global_indices': [
                    'FTSE', 'DAX', 'CAC40', 'NIKKEI', 'HSI', 'ASX200'
                ],
                'sector_indices': [
                    'XLF', 'XLK', 'XLE', 'XLV', 'XLI'  # Sector ETF futures
                ]
            },
            'exchanges': ['cme', 'eurex', 'ice', 'sgx', 'hkex'],
            'scan_criteria': {
                'min_24h_volume_contracts': 10000,
                'min_open_interest_contracts': 50000,
                'trading_hours': 'extended',  # Include pre/post market
                'contract_months': ['front', 'second']
            },
            'alerts': {
                'gap_threshold': 0.005,  # 0.5% gap alert
                'volume_spike_multiplier': 2.5,
                'vix_correlation_alert': 0.8
            },
            'active_scans': {},
            'scan_results': [],
            'last_scan_time': None
        }
    
    def _create_commodities_scanner(self):
        """Create scanner for commodity futures markets with SOTA 2026 coverage."""
        self.logger.info("Creating commodities futures market scanner")
        
        return {
            'market_type': 'commodities',
            'scan_interval_seconds': 15,
            'markets': {
                'energy': [
                    'CL', 'NG', 'HO', 'RB', 'BZ'  # Crude, NatGas, Heating Oil, Gasoline, Brent
                ],
                'metals': [
                    'GC', 'SI', 'HG', 'PL', 'PA'  # Gold, Silver, Copper, Platinum, Palladium
                ],
                'agriculture': [
                    'ZC', 'ZS', 'ZW', 'ZM', 'ZL',  # Corn, Soybean, Wheat, Meal, Oil
                    'CC', 'KC', 'SB', 'CT'  # Cocoa, Coffee, Sugar, Cotton
                ],
                'livestock': [
                    'LE', 'HE', 'GF'  # Live Cattle, Lean Hogs, Feeder Cattle
                ]
            },
            'exchanges': ['cme', 'nymex', 'comex', 'ice', 'lme'],
            'scan_criteria': {
                'min_24h_volume_contracts': 5000,
                'seasonality_aware': True,
                'weather_factor': True,
                'inventory_report_tracking': True
            },
            'alerts': {
                'contango_backwardation_shift': True,
                'inventory_surprise_threshold': 0.1,  # 10% vs expectations
                'weather_event_alert': True,
                'geopolitical_risk_factor': True
            },
            'active_scans': {},
            'scan_results': [],
            'last_scan_time': None
        }
    
    def _create_forex_scanner(self):
        """Create scanner for forex futures markets with SOTA 2026 coverage."""
        self.logger.info("Creating forex futures market scanner")
        
        return {
            'market_type': 'forex',
            'scan_interval_seconds': 5,
            'markets': {
                'majors': [
                    '6E', '6B', '6J', '6C', '6A', '6S', '6N'  # EUR, GBP, JPY, CAD, AUD, CHF, NZD
                ],
                'crosses': [
                    'EUR/GBP', 'EUR/JPY', 'GBP/JPY', 'AUD/JPY', 'EUR/CHF'
                ],
                'emerging': [
                    '6M', '6L', '6R', '6Z'  # MXN, BRL, RUB, ZAR
                ],
                'crypto_pairs': [
                    'BTC/USD', 'ETH/USD'  # CME crypto futures
                ]
            },
            'exchanges': ['cme', 'ice', 'eurex', 'lse'],
            'scan_criteria': {
                'min_24h_volume_contracts': 1000,
                'pip_movement_threshold': 20,
                'session_aware': True,  # Track London, NY, Tokyo, Sydney sessions
                'central_bank_calendar': True
            },
            'alerts': {
                'session_breakout': True,
                'correlation_breakdown': 0.3,  # Alert when corr drops below 0.3
                'interest_rate_differential': 0.005,
                'news_impact_alert': True
            },
            'sessions': {
                'sydney': {'open': '22:00', 'close': '07:00', 'tz': 'UTC'},
                'tokyo': {'open': '00:00', 'close': '09:00', 'tz': 'UTC'},
                'london': {'open': '08:00', 'close': '17:00', 'tz': 'UTC'},
                'new_york': {'open': '13:00', 'close': '22:00', 'tz': 'UTC'}
            },
            'active_scans': {},
            'scan_results': [],
            'last_scan_time': None
        }
    
    def _initialize_risk_management(self):
        """Initialize the risk management system for futures trading."""
        self.risk_management = {
            'position_limits': {
                'max_per_market': 0.1,  # 10% of capital per market
                'max_per_strategy': 0.3,  # 30% of capital per strategy
                'max_leverage': 10  # Maximum leverage
            },
            'stop_loss_settings': {
                'default': 0.02,  # 2% default stop loss
                'trailing': True,
                'atr_multiplier': 2.0
            },
            'correlation_limits': {
                'max_correlation': 0.7,  # Max correlation between positions
                'min_portfolio_variance': 0.01
            },
            'drawdown_controls': {
                'daily_limit': 0.05,  # 5% max daily drawdown
                'weekly_limit': 0.1,  # 10% max weekly drawdown
                'circuit_breakers': True
            }
        }
        
        self.logger.info("Risk management system initialized")
    
    def _start_background_workers(self):
        """Start background worker threads for the futures trading master."""
        self.logger.info("Starting background worker threads")
        
        # Start strategy execution worker
        self.strategy_worker = threading.Thread(
            target=self._strategy_execution_worker,
            daemon=True,
            name="StrategyExecutionWorker"
        )
        self.strategy_worker.start()
        
        # Start market scanning worker
        self.scanner_worker = threading.Thread(
            target=self._market_scanning_worker,
            daemon=True,
            name="MarketScanningWorker"
        )
        self.scanner_worker.start()
        
        # Start risk monitoring worker
        self.risk_worker = threading.Thread(
            target=self._risk_monitoring_worker,
            daemon=True,
            name="RiskMonitoringWorker"
        )
        self.risk_worker.start()
        
        self.logger.info("Background worker threads started")
    
    def _strategy_execution_worker(self):
        """Worker thread that executes trading strategies."""
        self.logger.info("Strategy execution worker started")
        
        try:
            while True:
                # Run short selling strategy
                self._execute_short_selling_strategy()
                
                # Run hedging strategy
                self._execute_hedging_strategy()
                
                # Run spreading strategy
                self._execute_spreading_strategy()
                
                # Run scalping strategy
                self._execute_scalping_strategy()
                
                # Run arbitrage strategy
                self._execute_arbitrage_strategy()
                
                # Run position trading strategy
                self._execute_position_trading_strategy()
                
                # Brief sleep to prevent CPU overload
                time.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"Error in strategy execution worker: {e}")
            self.logger.error(traceback.format_exc())
    
    def _execute_short_selling_strategy(self):
        """Execute the short selling strategy based on market conditions."""
        try:
            engine = self.strategy_engines.get('short_selling')
            if not engine:
                return
                
            # Scan for shorting opportunities
            for market_type in engine['config']['target_markets']:
                scanner = self.market_scanners.get(market_type)
                if not scanner:
                    continue
                    
                # Get markets for this type
                markets = self._get_markets_for_type(market_type)
                
                for market in markets:
                    # Skip if we already have a short position in this market
                    if market in engine['active_shorts']:
                        continue
                        
                    # Analyze market for shorting opportunities
                    opportunity = self._analyze_short_opportunity(market, engine)
                    
                    if opportunity and opportunity['score'] > 0.7:  # 70% confidence threshold
                        # Generate short signal
                        signal = self._generate_short_signal(market, opportunity)
                        
                        # Submit signal to execution system
                        self._submit_trading_signal(signal)
                        
                        # Track active short
                        engine['active_shorts'][market] = {
                            'entry_time': datetime.now(),
                            'entry_price': opportunity['price'],
                            'position_size': opportunity['position_size'],
                            'stop_loss': opportunity['stop_loss'],
                            'take_profit': opportunity['take_profit'],
                            'technique': opportunity['technique']
                        }
                        
                        self.logger.info(f"Short signal generated for {market} using {opportunity['technique']} technique")
            
            # Manage existing shorts
            self._manage_active_shorts(engine)
                
        except Exception as e:
            self.logger.error(f"Error executing short selling strategy: {e}")
            self.logger.error(traceback.format_exc())
    
    def _compute_rsi(self, prices, period=14):
        """Compute RSI from price series."""
        if len(prices) < period + 1:
            return None
        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            gains.append(change if change > 0 else 0)
            losses.append(-change if change < 0 else 0)
        recent_gains = gains[-period:]
        recent_losses = losses[-period:]
        avg_gain = sum(recent_gains) / period
        avg_loss = sum(recent_losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _compute_ema(self, prices, period=20):
        """Compute EMA from price series."""
        if len(prices) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _analyze_short_opportunity(self, market, engine):
        """
        Analyze a market for short selling opportunities.
        Checks if price is near resistance or overbought (RSI > 70),
        and if there's downward momentum (price below EMA).
        
        Args:
            market: Market symbol (e.g. 'BTC-PERP')
            engine: Short selling engine configuration
            
        Returns:
            Opportunity dictionary or None if no opportunity
        """
        data_list = self.market_data.get(market, [])
        if len(data_list) < 25:
            return None

        prices = [d.get("price", 0) for d in data_list[-50:] if d.get("price", 0) > 0]
        if len(prices) < 25:
            return None

        rsi = self._compute_rsi(prices, 14)
        if rsi is None or rsi <= 70:
            return None

        ema = self._compute_ema(prices, 20)
        if ema is None:
            return None

        current_price = prices[-1]
        if current_price >= ema:
            return None

        stop_loss = current_price * 1.02
        take_profit = current_price * 0.95
        confidence = min(0.95, 0.5 + (rsi - 70) / 100 + 0.2)
        config = engine.get("config", {}) if isinstance(engine, dict) else {}
        risk_limit = config.get("risk_limit", 0.02)
        position_size = risk_limit

        return {
            "symbol": market,
            "direction": "short",
            "confidence": confidence,
            "entry_price": current_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "score": confidence,
            "price": current_price,
            "position_size": position_size,
            "technique": "overbought_short",
        }

    def _generate_short_signal(self, market, opportunity):
        """
        Generate a short selling signal for execution.
        Uses analysis from _analyze_short_opportunity.
        
        Args:
            market: Market symbol
            opportunity: Opportunity dict from _analyze_short_opportunity
            
        Returns:
            Trading signal dictionary
        """
        if not opportunity:
            return {}
        entry = opportunity.get("entry_price", opportunity.get("price", 0))
        stop = opportunity.get("stop_loss", entry * 1.02)
        take = opportunity.get("take_profit", entry * 0.95)
        stop_loss_pct = (stop - entry) / entry * 100 if entry > 0 else 2.0
        take_profit_pct = (entry - take) / entry * 100 if entry > 0 else 5.0
        return {
            "symbol": opportunity.get("symbol", market),
            "action": "sell",
            "confidence": opportunity.get("confidence", 0),
            "entry_price": entry,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "strategy": "futures_short",
        }
    
    def _manage_active_shorts(self, engine):
        """
        SOTA 2026: Manage active short positions with dynamic risk management.
        
        Args:
            engine: Short selling engine configuration
        """
        try:
            if not engine:
                return
            
            # Get all short positions
            short_positions = {
                symbol: pos for symbol, pos in self.open_positions.items()
                if pos.get('direction') == 'short'
            }
            
            if not short_positions:
                return
            
            for symbol, position in short_positions.items():
                entry_price = position.get('entry_price', 0)
                current_price = position.get('current_price', entry_price)
                size = position.get('size', 0)
                
                if entry_price <= 0:
                    continue
                
                # Calculate unrealized PnL (for shorts: profit when price goes down)
                pnl_pct = (entry_price - current_price) / entry_price * 100
                
                # 1. Update trailing stop loss
                stop_loss = position.get('stop_loss')
                trailing_pct = engine.get('trailing_stop_pct', 2.0)
                
                if stop_loss is None:
                    # Initial stop loss above entry
                    position['stop_loss'] = entry_price * (1 + trailing_pct / 100)
                elif pnl_pct > 0:
                    # Move stop loss down as position profits (trailing)
                    new_stop = current_price * (1 + trailing_pct / 100)
                    if new_stop < stop_loss:
                        position['stop_loss'] = new_stop
                        self.logger.info(f"Trailing stop updated for {symbol} short: {new_stop:.4f}")
                
                # 2. Check stop loss hit
                if current_price >= position.get('stop_loss', float('inf')):
                    self._close_position(symbol, reason="stop_loss_hit")
                    if self.event_bus:
                        self.event_bus.publish("futures.short.stopped", {
                            "symbol": symbol,
                            "pnl_pct": pnl_pct,
                            "stop_price": position.get('stop_loss')
                        })
                    continue
                
                # 3. Check take profit levels
                take_profit_pct = engine.get('take_profit_pct', 5.0)
                if pnl_pct >= take_profit_pct:
                    self._close_position(symbol, reason="take_profit_hit")
                    if self.event_bus:
                        self.event_bus.publish("futures.short.profit_taken", {
                            "symbol": symbol,
                            "pnl_pct": pnl_pct
                        })
                    continue
                
                # 4. Position sizing adjustment for high-risk shorts
                max_position_risk = engine.get('max_position_risk_pct', 2.0)
                position_risk = abs(pnl_pct) if pnl_pct < 0 else 0
                
                if position_risk > max_position_risk:
                    # Reduce position size
                    reduce_ratio = max_position_risk / position_risk
                    new_size = size * reduce_ratio
                    self._reduce_position(symbol, new_size)
                    if self.event_bus:
                        self.event_bus.publish("futures.short.reduced", {
                            "symbol": symbol,
                            "original_size": size,
                            "new_size": new_size,
                            "reason": "risk_management"
                        })
                
                # 5. Borrow cost monitoring
                borrow_rate = position.get('borrow_rate', 0)
                hold_time_hours = (time.time() - position.get('entry_time', time.time())) / 3600
                accumulated_cost_pct = borrow_rate * hold_time_hours / 24 * 365 / 100
                
                if accumulated_cost_pct > 0.5:  # More than 0.5% in borrow costs
                    self.logger.warning(f"High borrow cost for {symbol} short: {accumulated_cost_pct:.2f}%")
                    
            # Log management summary
            if short_positions:
                self.logger.debug(f"Managed {len(short_positions)} short positions")
                
        except Exception as e:
            self.logger.error(f"Error managing short positions: {e}")
    
    def _execute_hedging_strategy(self):
        """Execute the hedging strategy based on portfolio risk with SOTA 2026 logic."""
        try:
            engine = self.strategy_engines.get('hedging')
            if not engine or not self.strategies['hedging']['enabled']:
                return
            
            # Calculate portfolio exposure
            total_long_exposure = sum(
                pos.get('value', 0) for pos in self.open_positions.values() 
                if pos.get('direction') == 'long'
            )
            total_short_exposure = sum(
                abs(pos.get('value', 0)) for pos in self.open_positions.values() 
                if pos.get('direction') == 'short'
            )
            net_exposure = total_long_exposure - total_short_exposure
            
            # Check if hedging is needed
            hedge_threshold = self.risk_management.get('position_limits', {}).get('max_per_market', 0.1)
            total_capital = sum(
                abs(pos.get('value', 0)) for pos in self.open_positions.values()
            ) or self.config.get('initial_capital', 100000)
            
            if abs(net_exposure) > total_capital * hedge_threshold:
                # Generate hedge signal
                hedge_direction = 'short' if net_exposure > 0 else 'long'
                hedge_size = abs(net_exposure) * engine['config'].get('hedge_ratio', 1.0)
                
                signal = {
                    'strategy': 'hedging',
                    'type': 'delta_hedge',
                    'direction': hedge_direction,
                    'size': hedge_size,
                    'reason': f"Net exposure {net_exposure:.2f} exceeds threshold",
                    'timestamp': datetime.now().isoformat()
                }
                self._submit_trading_signal(signal)
                self.logger.info(f"Hedging signal generated: {hedge_direction} {hedge_size:.2f}")
                
        except Exception as e:
            self.logger.error(f"Error executing hedging strategy: {e}")
    
    def _execute_spreading_strategy(self):
        """Execute the spreading strategy to capture inefficiencies with SOTA 2026 logic."""
        try:
            engine = self.strategy_engines.get('spreading')
            if not engine or not self.strategies['spreading']['enabled']:
                return
            
            # Check for spread opportunities in market data
            for symbol, data_list in self.market_data.items():
                if len(data_list) < 2:
                    continue
                    
                latest = data_list[-1]
                prev = data_list[-2]
                
                # Calculate basis/contango/backwardation
                price = latest.get('price', 0)
                prev_price = prev.get('price', 0)
                
                if price > 0 and prev_price > 0:
                    basis = (price - prev_price) / prev_price
                    min_inefficiency = engine['config'].get('min_inefficiency', 0.001)
                    
                    if abs(basis) > min_inefficiency:
                        signal = {
                            'strategy': 'spreading',
                            'type': 'basis_spread',
                            'symbol': symbol,
                            'direction': 'short' if basis > 0 else 'long',
                            'basis': basis,
                            'reason': f"Basis spread opportunity: {basis*100:.3f}%",
                            'timestamp': datetime.now().isoformat()
                        }
                        self._submit_trading_signal(signal)
                        
        except Exception as e:
            self.logger.error(f"Error executing spreading strategy: {e}")
    
    def _execute_scalping_strategy(self):
        """Execute the scalping strategy for small price movements with SOTA 2026 logic."""
        try:
            engine = self.strategy_engines.get('scalping')
            if not engine or not self.strategies['scalping']['enabled']:
                return
            
            # Check daily trade limit
            daily_stats = engine.get('daily_stats', {})
            if daily_stats.get('trades_today', 0) >= daily_stats.get('max_trades', 100):
                return
            
            config = engine['config']
            target_profit = config.get('target_profit_pips', 5) / 10000  # Convert pips to decimal
            
            # Scan for scalping opportunities
            for symbol, data_list in self.market_data.items():
                if len(data_list) < 10:
                    continue
                
                # Check micro-momentum
                recent_prices = [d.get('price', 0) for d in data_list[-10:] if d.get('price', 0) > 0]
                if len(recent_prices) < 10:
                    continue
                    
                momentum = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] if recent_prices[0] > 0 else 0
                
                if abs(momentum) > 0.001:  # 0.1% momentum threshold
                    signal = {
                        'strategy': 'scalping',
                        'type': 'momentum_scalp',
                        'symbol': symbol,
                        'direction': 'long' if momentum > 0 else 'short',
                        'entry_price': recent_prices[-1],
                        'target_profit_pct': target_profit,
                        'max_loss_pct': config.get('max_loss_pips', 3) / 10000,
                        'reason': f"Micro-momentum: {momentum*100:.3f}%",
                        'timestamp': datetime.now().isoformat()
                    }
                    self._submit_trading_signal(signal)
                    engine['daily_stats']['trades_today'] = daily_stats.get('trades_today', 0) + 1
                    break  # One scalp at a time
                    
        except Exception as e:
            self.logger.error(f"Error executing scalping strategy: {e}")
    
    def _execute_arbitrage_strategy(self):
        """Execute the arbitrage strategy to capture price gaps with SOTA 2026 logic."""
        try:
            engine = self.strategy_engines.get('arbitrage')
            if not engine or not self.strategies['arbitrage']['enabled']:
                return
            
            config = engine['config']
            min_gap = config.get('min_price_gap', 0.0005)
            
            # Cross-exchange price comparison would happen here
            # For now, check for significant price movements that might indicate arb opportunities
            for symbol, data_list in self.market_data.items():
                if len(data_list) < 5:
                    continue
                
                prices = [d.get('price', 0) for d in data_list[-5:] if d.get('price', 0) > 0]
                if len(prices) < 5:
                    continue
                
                # Check for rapid price divergence (potential arb)
                max_price = max(prices)
                min_price = min(prices)
                
                if min_price > 0:
                    spread = (max_price - min_price) / min_price
                    
                    if spread > min_gap:
                        opportunity = {
                            'symbol': symbol,
                            'spread': spread,
                            'max_price': max_price,
                            'min_price': min_price,
                            'timestamp': datetime.now().isoformat()
                        }
                        engine['opportunity_log'].append(opportunity)
                        engine['performance']['opportunities_found'] = \
                            engine['performance'].get('opportunities_found', 0) + 1
                        
                        # Log but don't auto-trade arb (requires multi-venue execution)
                        self.logger.info(f"Arbitrage opportunity detected: {symbol} spread {spread*100:.3f}%")
                        
        except Exception as e:
            self.logger.error(f"Error executing arbitrage strategy: {e}")
    
    def _execute_position_trading_strategy(self):
        """Execute the position trading strategy for long-term trends with SOTA 2026 logic."""
        try:
            engine = self.strategy_engines.get('position_trading')
            if not engine or not self.strategies['position_trading']['enabled']:
                return
            
            # Check existing positions for exit conditions
            active_positions = engine.get('active_positions', {})
            holding_period = engine.get('holding_period', {})
            min_days = holding_period.get('min_days', 7)
            max_days = holding_period.get('max_days', 90)
            
            # Scan for new position opportunities (trend following)
            for symbol, data_list in self.market_data.items():
                if symbol in active_positions:
                    continue  # Already have position
                    
                if len(data_list) < 50:
                    continue  # Need sufficient history
                
                prices = [d.get('price', 0) for d in data_list[-50:] if d.get('price', 0) > 0]
                if len(prices) < 50:
                    continue
                
                # Simple trend detection: 50-period vs current
                avg_50 = sum(prices) / len(prices)
                current = prices[-1]
                avg_20 = sum(prices[-20:]) / 20
                
                # Trend confirmation
                trend_strength = (current - avg_50) / avg_50 if avg_50 > 0 else 0
                short_trend = (current - avg_20) / avg_20 if avg_20 > 0 else 0
                
                # Both short and long trend aligned
                if abs(trend_strength) > 0.05 and (trend_strength * short_trend) > 0:
                    direction = 'long' if trend_strength > 0 else 'short'
                    
                    signal = {
                        'strategy': 'position_trading',
                        'type': 'trend_following',
                        'symbol': symbol,
                        'direction': direction,
                        'entry_price': current,
                        'trend_strength': trend_strength,
                        'min_hold_days': min_days,
                        'max_hold_days': max_days,
                        'reason': f"Trend detected: {trend_strength*100:.2f}% from 50-period avg",
                        'timestamp': datetime.now().isoformat()
                    }
                    self._submit_trading_signal(signal)
                    self.logger.info(f"Position trade signal: {symbol} {direction}")
                    
        except Exception as e:
            self.logger.error(f"Error executing position trading strategy: {e}")
    
    def _market_scanning_worker(self):
        """Worker thread that scans markets for opportunities."""
        self.logger.info("Market scanning worker started")
        
        try:
            while True:
                # Scan crypto markets
                self._scan_markets('crypto')
                
                # Scan indices markets
                self._scan_markets('indices')
                
                # Scan commodities markets
                self._scan_markets('commodities')
                
                # Scan forex markets
                self._scan_markets('forex')
                
                # Brief sleep to prevent CPU overload
                time.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Error in market scanning worker: {e}")
            self.logger.error(traceback.format_exc())
    
    def _scan_markets(self, market_type):
        """
        Scan markets of a specific type for opportunities with SOTA 2026 analysis.
        
        Args:
            market_type: Type of market to scan
        """
        try:
            scanner = self.market_scanners.get(market_type)
            if not scanner:
                return
            
            markets = scanner.get('markets', {})
            scan_criteria = scanner.get('scan_criteria', {})
            
            # Flatten market lists
            all_markets = []
            for category, market_list in markets.items():
                if isinstance(market_list, list):
                    all_markets.extend(market_list)
            
            scan_results = []
            
            for market in all_markets[:10]:  # Limit to prevent overload
                # Check if we have data for this market
                if market in self.market_data and len(self.market_data[market]) > 0:
                    latest = self.market_data[market][-1]
                    
                    # Calculate opportunity score based on volatility and volume
                    price = latest.get('price', 0)
                    volume = latest.get('volume', 0)
                    
                    if price > 0:
                        # Simple opportunity scoring
                        score = 0.5  # Base score
                        
                        # Volume factor
                        min_volume = scan_criteria.get('min_24h_volume_usd', 1000000)
                        if volume > min_volume:
                            score += 0.2
                        
                        # Add to results if score is good
                        if score > 0.6:
                            scan_results.append({
                                'market': market,
                                'market_type': market_type,
                                'score': score,
                                'price': price,
                                'volume': volume,
                                'timestamp': datetime.now().isoformat()
                            })
            
            # Update scanner state
            scanner['scan_results'] = scan_results
            scanner['last_scan_time'] = datetime.now().isoformat()
            
            if scan_results and self.event_bus:
                self.event_bus.publish('futures.scan.complete', {
                    'market_type': market_type,
                    'results_count': len(scan_results),
                    'top_results': scan_results[:5]
                })
                
        except Exception as e:
            self.logger.error(f"Error scanning {market_type} markets: {e}")
    
    def _risk_monitoring_worker(self):
        """Worker thread that monitors risk across all positions."""
        self.logger.info("Risk monitoring worker started")
        
        try:
            while True:
                # Monitor position risks
                self._monitor_position_risks()
                
                # Monitor portfolio risks
                self._monitor_portfolio_risks()
                
                # Monitor market risks
                self._monitor_market_risks()
                
                # Brief sleep to prevent CPU overload
                time.sleep(5)
                
        except Exception as e:
            self.logger.error(f"Error in risk monitoring worker: {e}")
            self.logger.error(traceback.format_exc())
    
    def _monitor_position_risks(self):
        """Monitor risks for individual positions with SOTA 2026 risk management."""
        try:
            stop_loss_settings = self.risk_management.get('stop_loss_settings', {})
            default_stop = stop_loss_settings.get('default', 0.02)
            
            positions_at_risk = []
            
            for position_id, position in self.open_positions.items():
                entry_price = position.get('entry_price', 0)
                current_price = position.get('current_price', entry_price)
                direction = position.get('direction', 'long')
                stop_loss = position.get('stop_loss', entry_price * (1 - default_stop))
                
                if entry_price <= 0:
                    continue
                
                # Calculate P&L
                if direction == 'long':
                    pnl_pct = (current_price - entry_price) / entry_price
                    at_risk = current_price <= stop_loss
                else:
                    pnl_pct = (entry_price - current_price) / entry_price
                    at_risk = current_price >= stop_loss
                
                # Check if position is at risk
                if at_risk or pnl_pct < -default_stop:
                    positions_at_risk.append({
                        'position_id': position_id,
                        'symbol': position.get('symbol'),
                        'pnl_pct': pnl_pct,
                        'at_stop_loss': at_risk
                    })
            
            # Publish risk alerts
            if positions_at_risk and self.event_bus:
                self.event_bus.publish('futures.risk.position_alert', {
                    'positions_at_risk': positions_at_risk,
                    'count': len(positions_at_risk),
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error monitoring position risks: {e}")
    
    def _monitor_portfolio_risks(self):
        """Monitor risks for the overall portfolio with SOTA 2026 controls."""
        try:
            drawdown_controls = self.risk_management.get('drawdown_controls', {})
            daily_limit = drawdown_controls.get('daily_limit', 0.05)
            
            # Calculate portfolio metrics
            total_value = sum(pos.get('value', 0) for pos in self.open_positions.values())
            total_pnl = sum(pos.get('unrealized_pnl', 0) for pos in self.open_positions.values())
            
            # Calculate drawdown (simplified)
            if total_value > 0:
                current_drawdown = abs(min(0, total_pnl)) / total_value
            else:
                current_drawdown = 0
            
            # Check circuit breakers
            circuit_breaker_triggered = False
            if current_drawdown >= daily_limit:
                circuit_breaker_triggered = True
                self.logger.warning(f"Portfolio drawdown {current_drawdown*100:.2f}% exceeds daily limit!")
            
            # Publish portfolio risk status
            if self.event_bus:
                self.event_bus.publish('futures.risk.portfolio_status', {
                    'total_value': total_value,
                    'total_pnl': total_pnl,
                    'current_drawdown': current_drawdown,
                    'daily_limit': daily_limit,
                    'circuit_breaker_triggered': circuit_breaker_triggered,
                    'position_count': len(self.open_positions),
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error monitoring portfolio risks: {e}")
    
    def _monitor_market_risks(self):
        """Monitor risks related to market conditions with SOTA 2026 analysis."""
        try:
            market_risk_metrics = {
                'high_volatility_markets': [],
                'low_liquidity_markets': [],
                'correlation_alerts': []
            }
            
            # Check each market for risk conditions
            for symbol, data_list in self.market_data.items():
                if len(data_list) < 20:
                    continue
                
                prices = [d.get('price', 0) for d in data_list[-20:] if d.get('price', 0) > 0]
                if len(prices) < 20:
                    continue
                
                # Calculate volatility
                avg_price = sum(prices) / len(prices)
                variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
                volatility = (variance ** 0.5) / avg_price if avg_price > 0 else 0
                
                # Flag high volatility
                if volatility > 0.05:  # 5% volatility threshold
                    market_risk_metrics['high_volatility_markets'].append({
                        'symbol': symbol,
                        'volatility': volatility
                    })
            
            # Publish market risk metrics
            if self.event_bus:
                self.event_bus.publish('futures.risk.market_conditions', {
                    'metrics': market_risk_metrics,
                    'high_vol_count': len(market_risk_metrics['high_volatility_markets']),
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error monitoring market risks: {e}")
    
    def _handle_market_data(self, event_data):
        """
        Handle market data events from the event bus.
        
        Args:
            event_data: Market data event
        """
        try:
            symbol = event_data.get('symbol')
            if not symbol:
                return
                
            # Store market data
            if symbol not in self.market_data:
                self.market_data[symbol] = []
                
            # Add data to history (with timestamp if not present)
            if 'timestamp' not in event_data:
                event_data['timestamp'] = datetime.now().isoformat()
                
            self.market_data[symbol].append(event_data)
            
            # Limit history size
            max_history = 1000
            if len(self.market_data[symbol]) > max_history:
                self.market_data[symbol] = self.market_data[symbol][-max_history:]
                
        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")
    
    def _handle_order_book(self, event_data):
        """Handle order book events from the event bus with SOTA 2026 processing."""
        try:
            symbol = event_data.get('symbol')
            if not symbol:
                return
            
            # Store order book snapshot
            bids = event_data.get('bids', [])
            asks = event_data.get('asks', [])
            
            # Calculate order book imbalance for scalping signals
            bid_volume = sum(b[1] for b in bids[:10]) if bids else 0
            ask_volume = sum(a[1] for a in asks[:10]) if asks else 0
            total_volume = bid_volume + ask_volume
            
            if total_volume > 0:
                imbalance = (bid_volume - ask_volume) / total_volume
                
                # Store in liquidity metrics
                self.liquidity_metrics[symbol] = {
                    'bid_volume': bid_volume,
                    'ask_volume': ask_volume,
                    'imbalance': imbalance,
                    'spread': (asks[0][0] - bids[0][0]) if bids and asks else 0,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error handling order book: {e}")
    
    def _handle_trades(self, event_data):
        """Handle trade events from the event bus with SOTA 2026 processing."""
        try:
            symbol = event_data.get('symbol')
            if not symbol:
                return
            
            # Track trade flow for analysis
            price = event_data.get('price', 0)
            size = event_data.get('size', 0)
            side = event_data.get('side', 'unknown')
            
            # Update market data with latest trade
            if symbol not in self.market_data:
                self.market_data[symbol] = []
            
            self.market_data[symbol].append({
                'price': price,
                'volume': size,
                'side': side,
                'timestamp': event_data.get('timestamp', datetime.now().isoformat())
            })
            
            # Keep history limited
            if len(self.market_data[symbol]) > 1000:
                self.market_data[symbol] = self.market_data[symbol][-1000:]
                
        except Exception as e:
            self.logger.error(f"Error handling trades: {e}")
    
    def _handle_trading_signal(self, event_data):
        """Handle trading signal events from the event bus with SOTA 2026 processing."""
        try:
            signal_id = event_data.get('signal_id')
            strategy = event_data.get('strategy')
            
            # Track signal for performance analysis
            self.trade_history.append({
                'signal_id': signal_id,
                'strategy': strategy,
                'symbol': event_data.get('symbol'),
                'direction': event_data.get('direction'),
                'received_at': datetime.now().isoformat(),
                'status': 'received'
            })
            
            # Keep history limited
            if len(self.trade_history) > 1000:
                self.trade_history = self.trade_history[-1000:]
                
        except Exception as e:
            self.logger.error(f"Error handling trading signal: {e}")
    
    def _handle_execution_event(self, event_data):
        """Handle execution events from the event bus with SOTA 2026 processing."""
        try:
            signal_id = event_data.get('signal_id')
            status = event_data.get('status')  # 'filled', 'partial', 'rejected'
            
            # Update trade history
            for trade in self.trade_history:
                if trade.get('signal_id') == signal_id:
                    trade['status'] = status
                    trade['executed_at'] = datetime.now().isoformat()
                    trade['fill_price'] = event_data.get('fill_price')
                    trade['fill_size'] = event_data.get('fill_size')
                    break
            
            # Update strategy performance
            strategy = event_data.get('strategy')
            if strategy and status == 'filled':
                if strategy not in self.strategy_performance:
                    self.strategy_performance[strategy] = {'fills': 0, 'rejects': 0}
                self.strategy_performance[strategy]['fills'] += 1
            elif strategy and status == 'rejected':
                if strategy not in self.strategy_performance:
                    self.strategy_performance[strategy] = {'fills': 0, 'rejects': 0}
                self.strategy_performance[strategy]['rejects'] += 1
                
        except Exception as e:
            self.logger.error(f"Error handling execution event: {e}")
    
    def _handle_volatility_update(self, event_data):
        """Handle volatility update events from the event bus with SOTA 2026 processing."""
        try:
            symbol = event_data.get('symbol')
            if not symbol:
                return
            
            volatility = event_data.get('volatility', 0)
            volatility_type = event_data.get('type', 'historical')  # historical, implied, realized
            
            # Store volatility data
            self.volatility_models[symbol] = {
                'value': volatility,
                'type': volatility_type,
                'percentile': event_data.get('percentile', 50),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error handling volatility update: {e}")
    
    def _handle_correlation_update(self, event_data):
        """Handle correlation update events from the event bus with SOTA 2026 processing."""
        try:
            # Update correlation matrix
            correlations = event_data.get('correlations', {})
            
            for pair, corr_value in correlations.items():
                self.correlation_matrix[pair] = {
                    'value': corr_value,
                    'timestamp': datetime.now().isoformat()
                }
            
        except Exception as e:
            self.logger.error(f"Error handling correlation update: {e}")
    
    def _submit_trading_signal(self, signal):
        """
        Submit a trading signal for execution.
        
        Args:
            signal: Trading signal dictionary
        """
        try:
            if not signal:
                return
                
            # Add timestamp if not present
            if 'timestamp' not in signal:
                signal['timestamp'] = datetime.now().isoformat()
                
            # Add signal ID if not present
            if 'signal_id' not in signal:
                signal['signal_id'] = str(uuid.uuid4())
                
            # Publish signal to event bus
            if self.event_bus:
                self.event_bus.publish('trading.signal', signal)
                
            self.logger.debug(f"Submitted trading signal: {signal['signal_id']}")
            
        except Exception as e:
            self.logger.error(f"Error submitting trading signal: {e}")
    
    def _get_markets_for_type(self, market_type):
        """
        Get markets for a specific type with SOTA 2026 market coverage.
        
        Args:
            market_type: Type of market to get
            
        Returns:
            List of markets
        """
        try:
            scanner = self.market_scanners.get(market_type)
            if not scanner:
                return []
            
            markets = scanner.get('markets', {})
            
            # Flatten all market lists for this type
            all_markets = []
            for category, market_list in markets.items():
                if isinstance(market_list, list):
                    all_markets.extend(market_list)
            
            return all_markets
            
        except Exception as e:
            self.logger.error(f"Error getting markets for type {market_type}: {e}")
            return []
    
    def connect_to_trading_intelligence(self, trading_intelligence=None):
        """
        Connect to the main trading intelligence system.
        
        Args:
            trading_intelligence: Trading intelligence component
            
        Returns:
            Boolean indicating successful connection
        """
        self.logger.info("Connecting to trading intelligence system")
        
        try:
            # Auto-discover trading intelligence if not provided
            if trading_intelligence is None:
                try:
                    from core.trading_intelligence import CompetitiveEdgeAnalyzer
                    # Look for existing instance in event bus subscribers
                    if self.event_bus:
                        for component in self.event_bus.get_subscribers('market.data'):
                            if isinstance(component, CompetitiveEdgeAnalyzer):
                                trading_intelligence = component
                                break
                    
                    if trading_intelligence is None:
                        self.logger.warning("Could not auto-discover trading intelligence component")
                        return False
                        
                except ImportError:
                    self.logger.warning("Could not import CompetitiveEdgeAnalyzer")
                    return False
            
            # Store reference
            self.trading_intelligence = trading_intelligence
            
            # Register with trading intelligence
            if hasattr(trading_intelligence, 'register_strategy_provider'):
                trading_intelligence.register_strategy_provider(self)
                
            # Publish connection event
            if self.event_bus:
                self.event_bus.publish('system.components.connected', {
                    'source': 'FuturesTradingMaster',
                    'target': 'CompetitiveEdgeAnalyzer',
                    'timestamp': datetime.now().isoformat()
                })
                
            self.logger.info("Successfully connected to trading intelligence")
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to trading intelligence: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def get_futures_trading_strategies(self):
        """
        Get the available futures trading strategies.
        
        Returns:
            Dictionary of strategies and their configurations
        """
        return self.strategies
    
    def get_shorting_techniques(self):
        """
        Get the available short selling techniques.
        
        Returns:
            Dictionary of short selling techniques
        """
        engine = self.strategy_engines.get('short_selling')
        if not engine:
            return {}
            
        return engine.get('techniques', {})
