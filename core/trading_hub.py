#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Trading Hub

Central trading hub that connects all trading components and orchestrates 
the trillion-dollar profit strategy across global markets, utilizing quantum
optimization and competitive edge analysis.
"""

import logging
import time
import threading
import traceback
from datetime import datetime

# Kingdom AI imports
from core.base_component import BaseComponent
from core.trading_intelligence import CompetitiveEdgeAnalyzer

# Lazy import for QuantumTradingOptimizer to prevent NumPy binary incompatibility at startup
def get_quantum_trading_optimizer():
    """Lazily import QuantumTradingOptimizer only when needed
    
    Ensures that Redis quantum nexus integration is preserved for all components
    by properly initializing the optimizer with Redis connection capabilities.
    """
    try:
        # Import after application startup to avoid NumPy binary incompatibility
        from core.quantum_trading_optimizer import QuantumTradingOptimizer
        
        # Log that we're getting the optimizer with Redis quantum nexus capabilities
        logging.info("Initializing QuantumTradingOptimizer with Redis quantum nexus integration")
        
        # Return the optimizer class that will get package data from Redis quantum nexus
        return QuantumTradingOptimizer
    except ImportError as e:
        logging.warning(f"QuantumTradingOptimizer not available: {e}")
        return None


class TradingHub(BaseComponent):
    """
    Central hub for the Kingdom AI trading system, coordinating all trading components
    and orchestrating the trillion-dollar profit strategy across global markets.
    
    This component serves as the unified command center that:
    1. Connects all trading components (intelligence, execution, optimization)
    2. Coordinates global trading strategies across all market types
    3. Prioritizes opportunities based on profit potential
    4. Tracks progress toward the $2 trillion profit goal
    5. Dynamically allocates resources to the most profitable markets
    6. Ensures 24/7 continuous operation and learning
    """
    
    def __init__(self, event_bus=None, config=None):
        """
        Initialize the trading hub with event bus connection.
        
        Args:
            event_bus: The event bus for publishing and subscribing to events
            config: Configuration parameters for the hub
        """
        super().__init__("TradingHub", event_bus, config)
        self.event_bus = event_bus
        self.config = config or {}
        self.logger = logging.getLogger('KingdomAI.TradingHub')
        
        # Core profit tracking (thread-safe with _data_lock)
        import threading
        self._data_lock = threading.Lock()
        self.profit_target = 2_000_000_000_000
        self.current_profit = 0
        self.daily_profit_history = {}
        self.strategy_profits = {}
        self.market_profits = {}
        
        # KAIG SURVIVAL FLOOR — must be met BEFORE chasing $2T
        # $26K realized gains → $13K to KAIG treasury (50% buyback) → launch funding
        # Creator capital only, 0 consumer users. This is existential.
        self.kaig_survival_floor_usd = 26_000
        self.kaig_treasury_target_usd = 13_000
        self.kaig_survival_met = False
        self._kaig_directive = {}
        
        # Component references
        self.trading_intelligence = None
        self.quantum_optimizer = None
        self.execution_engine = None
        
        # Status tracking
        self.system_status = "initializing"
        self.component_status = {}
        self.last_status_update = datetime.now()
        
        # Performance metrics
        self.performance_metrics = {
            'win_rate': 0,
            'avg_profit_per_trade': 0,
            'trades_per_second': 0,
            'capital_efficiency': 0
        }
        self.auto_trading_enabled = True
        
        # Initialize the hub
        self._initialize_hub()
        
    def _initialize_hub(self):
        """Initialize the trading hub and connect all components."""
        self.logger.info("Initializing Trading Hub")
        
        # Initialize event subscriptions
        self._setup_event_subscriptions()
        
        # Connect to components
        self._connect_components()
        
        # Start background threads
        self._start_background_threads()
        
        # Set system as ready
        self.system_status = "ready"
        self.logger.info("Trading Hub initialized and ready")
        
        # Publish system ready event
        if self.event_bus:
            self.event_bus.publish_sync('system.ready', {
                'component': 'TradingHub',
                'status': self.system_status,
                'profit_target': self.profit_target,
                'timestamp': datetime.now().isoformat()
            })
    
    def _setup_event_subscriptions(self):
        """Set up event bus subscriptions for the trading hub."""
        if not self.event_bus:
            self.logger.warning("No event bus provided, event subscriptions not set up")
            return
            
        self.logger.info("Setting up event subscriptions")
        
        # Subscribe to profit updates
        self.event_bus.subscribe_sync('trading.profit.update', self._handle_profit_update)
        
        # Subscribe to component status updates
        self.event_bus.subscribe_sync('system.component.status', self._handle_component_status)
        
        # Subscribe to trading opportunities
        self.event_bus.subscribe_sync('trading.opportunities.high_value', self._handle_high_value_opportunity)
        
        # Subscribe to strategy performance updates
        self.event_bus.subscribe_sync('trading.strategy.performance', self._handle_strategy_performance)
        
        # Subscribe to market updates
        self.event_bus.subscribe_sync('market.status', self._handle_market_status)
        
        # Subscribe to system commands
        self.event_bus.subscribe_sync('system.command', self._handle_system_command)
        
        # KAIG Intelligence Bridge — survival floor + ultimate target awareness
        self.event_bus.subscribe_sync('kaig.intel.trading.directive', self._handle_kaig_trading_directive)
        
        # SOTA 2026: Subscribe to chat/voice command events for system-wide control
        self.event_bus.subscribe_sync('trading.goal.set', self._handle_set_profit_goal)
        self.event_bus.subscribe_sync('trading.goal.daily', self._handle_set_daily_target)
        self.event_bus.subscribe_sync('trading.plan.acquire', self._handle_plan_acquire)
        self.event_bus.subscribe_sync('trading.plan.sell', self._handle_plan_sell)
        self.event_bus.subscribe_sync('trading.plan.update', self._handle_plan_update)
        self.event_bus.subscribe_sync('trading.plan.get', self._handle_plan_get)
        self.event_bus.subscribe_sync('trading.focus.market', self._handle_focus_market)
        self.event_bus.subscribe_sync('trading.analyze.asset', self._handle_analyze_asset)
        self.event_bus.subscribe_sync('trading.predator.enable', self._handle_predator_enable)
        self.event_bus.subscribe_sync('trading.predator.disable', self._handle_predator_disable)
        self.event_bus.subscribe_sync('trading.auto.start', self._handle_auto_trading_start)
        self.event_bus.subscribe_sync('trading.auto.stop', self._handle_auto_trading_stop)
        
        # Wire autonomous AI trading decisions from orchestrator
        self.event_bus.subscribe_sync('trading.autonomous.decision', self._handle_autonomous_decision)
        
        self.logger.info("Event subscriptions set up (including SOTA 2026 chat commands)")
    
    def _connect_components(self):
        """Connect to all required trading components."""
        self.logger.info("Connecting to trading components")
        
        # Connect to Trading Intelligence
        try:
            self.trading_intelligence = CompetitiveEdgeAnalyzer(self.event_bus, self.config.get('trading_intelligence', {}))
            self.component_status['trading_intelligence'] = "connected"
            self.logger.info("Connected to Trading Intelligence component")
        except Exception as e:
            self.logger.error(f"Error connecting to Trading Intelligence: {e}")
            self.component_status['trading_intelligence'] = "error"
        
        # Connect to Quantum Optimizer
        try:
            # Use the lazy loading function to get the QuantumTradingOptimizer class
            QuantumTradingOptimizerClass = get_quantum_trading_optimizer()
            if QuantumTradingOptimizerClass:
                self.quantum_optimizer = QuantumTradingOptimizerClass(self.event_bus, self.config.get('quantum_optimizer', {}))
                self.component_status['quantum_optimizer'] = "connected"
                self.logger.info("Connected to Quantum Trading Optimizer")
            else:
                self.logger.warning("Quantum Trading Optimizer not available")
                self.component_status['quantum_optimizer'] = "unavailable"
        except Exception as e:
            self.logger.error(f"Error connecting to Quantum Optimizer: {e}")
            self.component_status['quantum_optimizer'] = "error"
        
        # Connect components to each other
        if self.trading_intelligence and self.quantum_optimizer:
            try:
                self.quantum_optimizer.connect_to_trading_intelligence(self.trading_intelligence)
                self.logger.info("Quantum Optimizer connected to Trading Intelligence")
            except Exception as e:
                self.logger.error(f"Error connecting Quantum Optimizer to Trading Intelligence: {e}")
        
        self.logger.info(f"Component connection status: {self.component_status}")
    
    def _start_background_threads(self):
        """Start background threads for the trading hub."""
        self.logger.info("Starting background threads")
        self._shutdown_event = threading.Event()

        self.profit_tracking_thread = threading.Thread(
            target=self._profit_tracking_worker,
            daemon=True,
            name="ProfitTrackingThread"
        )
        self.profit_tracking_thread.start()
        
        # Start system monitoring thread
        self.system_monitoring_thread = threading.Thread(
            target=self._system_monitoring_worker,
            daemon=True,
            name="SystemMonitoringThread"
        )
        self.system_monitoring_thread.start()
        
        # Start strategy coordination thread
        self.strategy_coordination_thread = threading.Thread(
            target=self._strategy_coordination_worker,
            daemon=True,
            name="StrategyCoordinationThread"
        )
        self.strategy_coordination_thread.start()
        
        self.logger.info("Background threads started")
    
    def _profit_tracking_worker(self):
        """Worker thread that tracks progress toward the profit goal."""
        self.logger.info("Profit tracking worker started")
        
        try:
            while not self._shutdown_event.is_set():
                self._update_profit_metrics()
                self._generate_profit_report()
                self._check_progress_against_targets()
                self._shutdown_event.wait(60)
                
        except Exception as e:
            self.logger.error(f"Error in profit tracking worker: {e}")
            self.logger.error(traceback.format_exc())
    
    def _update_profit_metrics(self):
        """Update all profit-related metrics."""
        try:
            # Get current date for daily tracking
            today = datetime.now().date().isoformat()
            
            # Ensure today exists in history
            if today not in self.daily_profit_history:
                self.daily_profit_history[today] = 0
            
            # Calculate profit metrics
            total_trades = sum(self.strategy_profits.get(strategy, {}).get('trade_count', 0) 
                             for strategy in self.strategy_profits)
            
            if total_trades > 0:
                # Convert float to int or store in a different field if precision is needed
                self.performance_metrics['avg_profit_per_trade'] = int(self.current_profit / total_trades)
            
            # Calculate win rate
            total_wins = sum(self.strategy_profits.get(strategy, {}).get('wins', 0) 
                           for strategy in self.strategy_profits)
            
            if total_trades > 0:
                # Convert float to int or store in a different field if precision is needed
                self.performance_metrics['win_rate'] = int((total_wins / total_trades) * 100)
            
        except Exception as e:
            self.logger.error(f"Error updating profit metrics: {e}")
    
    def _generate_profit_report(self):
        """Generate and publish a profit report."""
        try:
            # Calculate progress percentage
            progress_pct = (self.current_profit / self.profit_target) * 100 if self.profit_target else 0
            survival_pct = (self.current_profit / self.kaig_survival_floor_usd) * 100 if self.kaig_survival_floor_usd else 0
            
            # Get top performing strategies
            top_strategies = sorted(
                self.strategy_profits.items(),
                key=lambda x: x[1].get('total_profit', 0),
                reverse=True
            )[:5]
            
            # Get top performing markets
            top_markets = sorted(
                self.market_profits.items(),
                key=lambda x: x[1].get('total_profit', 0),
                reverse=True
            )[:5]
            
            # Build report
            report = {
                'current_profit': self.current_profit,
                'profit_target': self.profit_target,
                'progress_percentage': progress_pct,
                'kaig_survival_floor_usd': self.kaig_survival_floor_usd,
                'kaig_survival_progress_pct': min(100, survival_pct),
                'kaig_survival_met': self.kaig_survival_met,
                'kaig_treasury_target_usd': self.kaig_treasury_target_usd,
                'top_strategies': [{k: v['total_profit']} for k, v in top_strategies],
                'top_markets': [{k: v['total_profit']} for k, v in top_markets],
                'performance_metrics': self.performance_metrics,
                'timestamp': datetime.now().isoformat()
            }
            
            # Publish report
            if self.event_bus:
                self.event_bus.publish_sync('trading.profit.report', report)
            
            # Log summary — show BOTH targets
            if not self.kaig_survival_met:
                self.logger.info(
                    f"Profit report: ${self.current_profit:,.2f} | "
                    f"KAIG SURVIVAL: {survival_pct:.1f}% of ${self.kaig_survival_floor_usd:,.0f} | "
                    f"$2T: {progress_pct:.6f}%")
            else:
                self.logger.info(
                    f"Profit report: ${self.current_profit:,.2f} / ${self.profit_target:,.2f} "
                    f"({progress_pct:.6f}%) | KAIG survival: MET ✓")
            
        except Exception as e:
            self.logger.error(f"Error generating profit report: {e}")
    
    def _check_progress_against_targets(self):
        """Check progress against profit targets and adjust strategies if needed.
        
        TWO DISTINCT TARGETS:
          1. KAIG SURVIVAL FLOOR: $26K realized → $13K treasury (existential, check FIRST)
          2. ULTIMATE TARGET: $2T (aspirational, always pursue)
        """
        try:
            # ── CHECK KAIG SURVIVAL FLOOR FIRST ──────────────────
            # This is existential. If not met, KAIG cannot launch.
            if not self.kaig_survival_met:
                survival_progress = (self.current_profit / self.kaig_survival_floor_usd) * 100 if self.kaig_survival_floor_usd else 0
                remaining = max(0, self.kaig_survival_floor_usd - self.current_profit)
                
                if self.current_profit >= self.kaig_survival_floor_usd:
                    self.kaig_survival_met = True
                    self.logger.info(
                        "═══ KAIG SURVIVAL FLOOR MET ═══ "
                        "$%.2f realized gains → $%.0f to KAIG treasury. "
                        "KAIG launch is funded. Now pursuing $2T ultimate target.",
                        self.current_profit, self.current_profit * 0.5)
                    if self.event_bus:
                        self.event_bus.publish_sync('kaig.survival.met', {
                            'realized_gains': self.current_profit,
                            'treasury_funded': self.current_profit * 0.5,
                            'timestamp': datetime.now().isoformat()
                        })
                else:
                    self.logger.warning(
                        "KAIG SURVIVAL: $%.2f / $%.0f (%.1f%%) — $%.0f more needed. "
                        "Creator capital only, 0 consumers. AGGRESSIVE MODE.",
                        self.current_profit, self.kaig_survival_floor_usd,
                        survival_progress, remaining)
                    # Force aggressive strategies until survival floor is met
                    self._adjust_strategies_for_higher_profit()
            
            # ── CHECK ULTIMATE $2T TARGET ────────────────────────
            progress_pct = (self.current_profit / self.profit_target) * 100 if self.profit_target else 0
            
            # Calculate daily target
            daily_target = self.profit_target / 365 / 5  # Amortized over 5 years
            
            # Get today's profit
            today = datetime.now().date().isoformat()
            today_profit = self.daily_profit_history.get(today, 0)
            
            # Check if we're below daily target
            if today_profit < daily_target:
                self.logger.warning(f"Daily profit (${today_profit:,.2f}) below $2T daily target (${daily_target:,.2f})")
                self._adjust_strategies_for_higher_profit()
            
        except Exception as e:
            self.logger.error(f"Error checking progress against targets: {e}")
    
    def _handle_kaig_trading_directive(self, event_data):
        """Receive KAIG trading directive — knows BOTH the survival floor and the $2T ultimate target.

        The survival floor is existential: $26K realized → $13K to KAIG treasury.
        The $2T is aspirational: always pursue, but survival comes FIRST.
        """
        try:
            if not isinstance(event_data, dict):
                return
            self._kaig_directive = event_data

            # Update survival floor from bridge config (in case runtime config changed)
            floor = event_data.get("kaig_survival_floor", {})
            if floor:
                new_floor = floor.get("required_realized_gains_usd", self.kaig_survival_floor_usd)
                new_treasury = floor.get("kaig_treasury_target_usd", self.kaig_treasury_target_usd)
                if new_floor != self.kaig_survival_floor_usd:
                    self.logger.info("KAIG survival floor updated: $%d → $%d", 
                                   self.kaig_survival_floor_usd, new_floor)
                    self.kaig_survival_floor_usd = new_floor
                    self.kaig_treasury_target_usd = new_treasury

                # Check if survival was already met (bridge tracks this too)
                if floor.get("survival_met", False) and not self.kaig_survival_met:
                    self.kaig_survival_met = True
                    self.logger.info("KAIG survival floor marked as MET by bridge")

            cycle = event_data.get("cycle", 0)
            if cycle <= 1 or cycle % 10 == 0:
                survival_pct = (self.current_profit / self.kaig_survival_floor_usd * 100
                               ) if self.kaig_survival_floor_usd else 0
                self.logger.info(
                    "KAIG Directive → TradingHub: survival=%s (%.1f%%), "
                    "profit=$%.2f, ultimate=$2T",
                    "MET" if self.kaig_survival_met else "NOT MET",
                    survival_pct, self.current_profit)
        except Exception as e:
            self.logger.error(f"Error handling KAIG trading directive: {e}")

    def _adjust_strategies_for_higher_profit(self):
        """Adjust trading strategies to achieve higher profit."""
        try:
            if self.quantum_optimizer:
                # Trigger more aggressive optimization
                self.logger.info("Triggering aggressive strategy optimization")
                
                if self.event_bus:
                    # Use publish_sync instead of publish to avoid coroutine not awaited warnings
                    self.event_bus.publish_sync('trading.strategy.optimize', {
                        'aggressiveness': 0.9,  # High aggressiveness
                        'priority': 'profit',
                        'timestamp': datetime.now().isoformat()
                    })
            
        except Exception as e:
            self.logger.error(f"Error adjusting strategies for higher profit: {e}")
    
    def _system_monitoring_worker(self):
        """Worker thread that monitors the system status."""
        self.logger.info("System monitoring worker started")
        
        try:
            while not self._shutdown_event.is_set():
                self._check_component_status()
                self._monitor_system_resources()
                self._check_for_alerts()
                self._shutdown_event.wait(10)
                
        except Exception as e:
            self.logger.error(f"Error in system monitoring worker: {e}")
            self.logger.error(traceback.format_exc())
    
    def _check_component_status(self):
        """Check the status of all connected components."""
        components = {
            'trading_intelligence': self.trading_intelligence,
            'quantum_optimizer': self.quantum_optimizer,
        }
        for name, comp in components.items():
            if comp is None:
                self.component_status[name] = 'unavailable'
            elif hasattr(comp, 'is_running') and not comp.is_running:
                self.component_status[name] = 'stopped'
            else:
                self.component_status[name] = 'active'
        if self.event_bus:
            self.event_bus.publish('trading.component.status', {
                'statuses': dict(self.component_status),
                'timestamp': datetime.now().isoformat()
            })

    def _monitor_system_resources(self):
        """Monitor system resources (CPU, memory, etc.)."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            self._system_resources = {
                'cpu_percent': cpu,
                'memory_percent': mem.percent,
                'memory_available_gb': round(mem.available / (1024**3), 2),
            }
            if cpu > 90 or mem.percent > 90:
                self.logger.warning("High resource usage: CPU=%.1f%% MEM=%.1f%%", cpu, mem.percent)
                if self.event_bus:
                    self.event_bus.publish('trading.resource.warning', self._system_resources)
        except ImportError:
            pass
        except Exception as e:
            self.logger.debug("Resource monitoring error: %s", e)

    def _check_for_alerts(self):
        """Check for system alerts that require attention."""
        alerts = []
        progress = (self.current_profit / self.profit_target * 100) if self.profit_target else 0
        if progress >= 100:
            alerts.append({'type': 'profit_target_reached', 'progress': progress})
        for comp, status in self.component_status.items():
            if status == 'error':
                alerts.append({'type': 'component_error', 'component': comp})
        if alerts and self.event_bus:
            self.event_bus.publish('trading.alerts', {
                'alerts': alerts, 'timestamp': datetime.now().isoformat()
            })
    
    def _strategy_coordination_worker(self):
        """Worker thread that coordinates trading strategies."""
        self.logger.info("Strategy coordination worker started")
        
        try:
            while not self._shutdown_event.is_set():
                self._coordinate_strategies()
                self._allocate_resources()
                self._shutdown_event.wait(30)
                
        except Exception as e:
            self.logger.error(f"Error in strategy coordination worker: {e}")
            self.logger.error(traceback.format_exc())
    
    def _coordinate_strategies(self):
        """Coordinate strategies across different markets and components."""
        with self._data_lock:
            if not self.strategy_profits:
                return
            ranked = sorted(self.strategy_profits.items(),
                            key=lambda kv: kv[1].get('total_profit', 0), reverse=True)
            active_symbols = list(getattr(self, 'market_profits', {}).keys())
        top_strategies = [s for s, _ in ranked[:5]]
        # Wire to CompetitiveEdgeAnalyzer
        try:
            ti = self.event_bus.get_component("trading_intelligence") if self.event_bus else None
            if ti is None:
                ti = self.trading_intelligence
            if ti and hasattr(ti, "analyze_market"):
                for symbol in active_symbols:
                    ti.analyze_market(symbol)
        except Exception as e:
            self.logger.debug("Trading intelligence wire: %s", e)
        if self.event_bus:
            self.event_bus.publish('trading.strategy.coordination', {
                'top_strategies': top_strategies,
                'strategy_count': len(self.strategy_profits),
                'timestamp': datetime.now().isoformat()
            })

    def _allocate_resources(self):
        """Allocate computational and capital resources to high-potential markets."""
        with self._data_lock:
            if not self.market_profits:
                return
            ranked = sorted(self.market_profits.items(),
                            key=lambda kv: kv[1].get('total_profit', 0), reverse=True)
        allocations = {}
        total = sum(max(0, v['total_profit']) for _, v in ranked) or 1
        for market, data in ranked:
            share = max(0, data['total_profit']) / total
            allocations[market] = round(share * 100, 1)
        if self.event_bus:
            self.event_bus.publish('trading.resource.allocation', {
                'allocations': allocations,
                'timestamp': datetime.now().isoformat()
            })
    
    def _handle_profit_update(self, event_data):
        """Handle profit update events from the event bus."""
        try:
            amount = event_data.get('amount', 0)
            strategy = event_data.get('strategy', 'unknown')
            market = event_data.get('market', 'unknown')
            timestamp = event_data.get('timestamp', datetime.now().isoformat())

            with self._data_lock:
                self.current_profit += amount

                day = datetime.fromisoformat(timestamp).date().isoformat()
                if day not in self.daily_profit_history:
                    self.daily_profit_history[day] = 0
                self.daily_profit_history[day] += amount

                if strategy not in self.strategy_profits:
                    self.strategy_profits[strategy] = {'total_profit': 0, 'trade_count': 0, 'wins': 0}
                self.strategy_profits[strategy]['total_profit'] += amount
                self.strategy_profits[strategy]['trade_count'] += 1
                if amount > 0:
                    self.strategy_profits[strategy]['wins'] += 1

                if market not in self.market_profits:
                    self.market_profits[market] = {'total_profit': 0, 'trade_count': 0}
                self.market_profits[market]['total_profit'] += amount
                self.market_profits[market]['trade_count'] += 1

            if amount >= 1000000:
                self.logger.info("Significant profit: $%s from %s in %s", f"{amount:,.2f}", strategy, market)

        except Exception as e:
            self.logger.error("Error handling profit update: %s", e)
    
    async def _handle_component_status(self, event_data):
        """Handle component status events from the event bus."""
        try:
            component = event_data.get('component')
            status = event_data.get('status')
            
            if component and status:
                self.component_status[component] = status
                
                # Log status changes
                self.logger.info(f"Component status update: {component} is {status}")
                
                # Check for errors
                if status == 'error':
                    self.logger.error(f"Component error: {component}")
                    # Attempt recovery
                    await self._attempt_component_recovery(component)
            
        except Exception as e:
            self.logger.error(f"Error handling component status: {e}")
            return None
    
    async def _attempt_component_recovery(self, component):
        """Attempt to recover a failed component by reinitializing it."""
        self.logger.info(f"Attempting to recover component: {component}")
        try:
            comp_name = component if isinstance(component, str) else getattr(component, '__class__', type(component)).__name__
            comp_obj = self.components.get(comp_name, component) if isinstance(component, str) else component
            if hasattr(comp_obj, 'initialize') and callable(comp_obj.initialize):
                result = await comp_obj.initialize()
                if result:
                    self.logger.info(f"Component {comp_name} recovered successfully")
                    if self.event_bus:
                        self.event_bus.publish("system.component.recovered", {"component": comp_name})
                    return True
                else:
                    self.logger.warning(f"Component {comp_name} recovery returned False")
                    return False
            else:
                self.logger.warning(f"Component {comp_name} has no initialize method")
                return False
        except Exception as e:
            self.logger.error(f"Component recovery failed for {component}: {e}")
            return False
    
    def _handle_high_value_opportunity(self, event_data):
        """Handle high-value trading opportunity events from the event bus."""
        try:
            count = event_data.get('count', 0)
            total_value = event_data.get('total_value', 0)
            
            self.logger.info(f"Received {count} high-value opportunities with total value: ${total_value:,.2f}")
            
            # Prioritize execution of high-value opportunities
            if self.event_bus:
                self.event_bus.publish('trading.execution.prioritize', {
                    'priority': 'high',
                    'reason': 'high_value_opportunities',
                    'count': count,
                    'timestamp': datetime.now().isoformat()
                })
            
        except Exception as e:
            self.logger.error(f"Error handling high-value opportunity: {e}")
    
    def _handle_strategy_performance(self, event_data):
        """Handle strategy performance events from the event bus."""
        try:
            strategy = event_data.get('strategy', 'unknown')
            win_rate = event_data.get('win_rate', 0)
            pnl = event_data.get('pnl', 0)
            if strategy not in self.strategy_profits:
                self.strategy_profits[strategy] = {'total_profit': 0, 'trade_count': 0, 'wins': 0}
            self.strategy_profits[strategy]['win_rate'] = win_rate
            self.strategy_profits[strategy]['latest_pnl'] = pnl
            if win_rate < 30:
                self.logger.warning("Strategy '%s' under-performing (%.1f%% win rate)", strategy, win_rate)
        except Exception as e:
            self.logger.error("Error handling strategy performance: %s", e)

    def _handle_market_status(self, event_data):
        """Handle market status events from the event bus."""
        try:
            market = event_data.get('market', 'unknown')
            status = event_data.get('status', 'unknown')
            volatility = event_data.get('volatility', 0)
            if not hasattr(self, '_market_statuses'):
                self._market_statuses = {}
            self._market_statuses[market] = {
                'status': status, 'volatility': volatility,
                'updated': datetime.now().isoformat()
            }
            if status == 'halted':
                self.logger.warning("Market %s HALTED", market)
        except Exception as e:
            self.logger.error("Error handling market status: %s", e)
    
    def _handle_system_command(self, event_data):
        """Handle system command events from the event bus."""
        try:
            command = event_data.get('command')
            params = event_data.get('params', {})
            
            if command == 'start_trading':
                self._start_trading(params)
            elif command == 'stop_trading':
                self._stop_trading(params)
            elif command == 'adjust_risk':
                self._adjust_risk(params)
            elif command == 'target_market':
                self._target_market(params)
            elif command == 'status_report':
                self._generate_status_report()
            else:
                self.logger.warning(f"Unknown system command: {command}")
            
        except Exception as e:
            self.logger.error(f"Error handling system command: {e}")
    
    def _start_trading(self, params):
        """Start trading with the specified parameters."""
        try:
            markets = params.get('markets', [])
            strategies = params.get('strategies', [])
            active_symbols = markets if markets else list(getattr(self, 'market_profits', {}).keys())
            
            self.logger.info(f"Starting trading with {len(strategies)} strategies across {len(markets)} markets")
            
            # Wire to CompetitiveEdgeAnalyzer
            try:
                ti = self.event_bus.get_component("trading_intelligence") if self.event_bus else None
                if ti is None:
                    ti = self.trading_intelligence
                if ti and hasattr(ti, "analyze_market"):
                    for symbol in active_symbols:
                        ti.analyze_market(symbol)
            except Exception as e:
                self.logger.debug("Trading intelligence wire: %s", e)
            
            if self.trading_intelligence and hasattr(self.trading_intelligence, 'start'):
                self.trading_intelligence.start()

            if self.quantum_optimizer and hasattr(self.quantum_optimizer, 'start'):
                self.quantum_optimizer.start()
            
            # Update system status
            self.system_status = "trading"
            
            # Publish trading started event
            if self.event_bus:
                self.event_bus.publish('trading.status', {
                    'status': 'started',
                    'markets': markets,
                    'strategies': strategies,
                    'timestamp': datetime.now().isoformat()
                })
            
        except Exception as e:
            self.logger.error(f"Error starting trading: {e}")
            self.logger.error(traceback.format_exc())
    
    def _stop_trading(self, params):
        """Stop trading with the specified parameters."""
        try:
            reason = params.get('reason', 'user_command')
            self.system_status = "stopped"
            self.logger.info("⛔ Trading stopped – reason: %s", reason)
            if self.event_bus:
                self.event_bus.publish('trading.status', {
                    'status': 'stopped', 'reason': reason,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error("Error stopping trading: %s", e)

    def _adjust_risk(self, params):
        """Adjust risk parameters for trading."""
        try:
            new_level = params.get('level', 'medium')
            max_drawdown = params.get('max_drawdown', None)
            self.logger.info("⚙️ Risk adjusted to level=%s, max_drawdown=%s", new_level, max_drawdown)
            if self.event_bus:
                self.event_bus.publish('trading.risk.adjusted', {
                    'level': new_level, 'max_drawdown': max_drawdown,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error("Error adjusting risk: %s", e)

    def _target_market(self, params):
        """Target a specific market for trading."""
        try:
            market = params.get('market', '')
            action = params.get('action', 'focus')
            self.logger.info("🎯 Targeting market: %s (action=%s)", market, action)
            if self.event_bus:
                self.event_bus.publish('trading.market.targeted', {
                    'market': market, 'action': action,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error("Error targeting market: %s", e)
    
    def _generate_status_report(self):
        """Generate a comprehensive status report."""
        try:
            # Build report data
            report = {
                'system_status': self.system_status,
                'component_status': self.component_status,
                'profit_metrics': {
                    'current_profit': self.current_profit,
                    'profit_target': self.profit_target,
                    'progress_percentage': (self.current_profit / self.profit_target) * 100 if self.profit_target else 0
                },
                'performance_metrics': self.performance_metrics,
                'active_strategies': len(self.strategy_profits),
                'active_markets': len(self.market_profits),
                'timestamp': datetime.now().isoformat()
            }
            
            # Publish report
            if self.event_bus:
                self.event_bus.publish('system.status.report', report)
            
            # Log summary
            self.logger.info(f"Status report generated: System is {self.system_status}, "
                           f"profit: ${self.current_profit:,.2f} / ${self.profit_target:,.2f}")
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating status report: {e}")
            self.logger.error(traceback.format_exc())
            return None
            
    def implement_trillion_dollar_strategy(self):
        """
        Implement the comprehensive trillion-dollar profit strategy across all systems.
        
        This method activates all components and coordinates them to work toward
        the $2 trillion profit goal with maximum efficiency and effectiveness.
        
        Returns:
            Boolean indicating successful implementation
        """
        self.logger.info("Implementing trillion-dollar profit strategy")
        
        try:
            # 1. Activate quantum trading optimizer
            if self.quantum_optimizer:
                # Use getattr to safely call method if it exists (avoids static type checker errors)
                detect_method = getattr(self.quantum_optimizer, 'detect_trillion_dollar_opportunities', None)
                scan_method = getattr(self.quantum_optimizer, '_scan_market_type', None)
                
                if detect_method and callable(detect_method):
                    detect_method()
                elif scan_method and callable(scan_method):
                    # Fallback to scanning all market types
                    for market_type in ['crypto', 'stocks', 'forex']:
                        scan_method(market_type)
                self.logger.info("Quantum trading optimizer activated")
            
            # 2. Activate trading intelligence
            if self.trading_intelligence:
                # Check if the method exists on the instance
                if hasattr(self.trading_intelligence, 'implement_trillion_dollar_strategy'):
                    self.logger.info("Using existing trillion dollar strategy implementation")
                    self.trading_intelligence.implement_trillion_dollar_strategy()
                else:
                    # Try to dynamically load the implementation if it's not available
                    try:
                        self.logger.info("Dynamically loading trillion dollar strategy implementation")
                        from core.trillion_dollar_strategy import apply_trillion_dollar_strategy_to_class
                        # Apply directly to the class
                        apply_trillion_dollar_strategy_to_class(self.trading_intelligence.__class__)
                        # Now call the method if it's available
                        if hasattr(self.trading_intelligence, 'implement_trillion_dollar_strategy'):
                            self.trading_intelligence.implement_trillion_dollar_strategy()
                        else:
                            self.logger.warning("Failed to dynamically add trillion dollar strategy method")
                    except Exception as e:
                        self.logger.error(f"Error loading trillion dollar strategy: {e}")
                        self.logger.error(traceback.format_exc())
                self.logger.info("Trading intelligence activated")
            
            # 3. Configure the profit tracking system
            self._configure_profit_tracking()
            
            # 4. Start high-performance trading mode
            self._start_high_performance_mode()
            
            # 5. Publish strategy activation event
            if self.event_bus:
                self.event_bus.publish('trading.strategy.trillion_dollar.activated', {
                    'component': 'TradingHub',
                    'timestamp': datetime.now().isoformat(),
                    'profit_target': self.profit_target
                })
            
            self.logger.info("Trillion-dollar strategy successfully implemented")
            return True
            
        except Exception as e:
            self.logger.error(f"Error implementing trillion-dollar strategy: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _configure_profit_tracking(self):
        """Configure the profit tracking system for the trillion-dollar strategy."""
        if not hasattr(self, 'daily_profit_history'):
            self.daily_profit_history = {}
        if not hasattr(self, 'strategy_profits'):
            self.strategy_profits = {}
        if not hasattr(self, 'market_profits'):
            self.market_profits = {}
        self.logger.info("📊 Profit tracking configured for trillion-dollar strategy")

    def _start_high_performance_mode(self):
        """Start high-performance trading mode for maximum throughput."""
        self.system_status = "high_performance"
        self.logger.info("🚀 High-performance trading mode ACTIVE")
        if self.event_bus:
            self.event_bus.publish('trading.mode.changed', {
                'mode': 'high_performance',
                'timestamp': datetime.now().isoformat()
            })
    
    # =========================================================================
    # SOTA 2026: Chat/Voice Command Handlers for System-Wide Control
    # =========================================================================
    
    def _handle_set_profit_goal(self, payload):
        """Handle set profit goal command from chat/voice."""
        try:
            amount_str = payload.get('amount', '')
            # Parse amount (handles "1 billion", "50 million", etc.)
            amount = self._parse_money_amount(amount_str)
            if amount:
                old_target = self.profit_target
                self.profit_target = amount
                self.logger.info(f"🎯 Profit goal updated: ${old_target:,.0f} → ${amount:,.0f}")
                
                if self.event_bus:
                    self.event_bus.publish('trading.goal.updated', {
                        'old_target': old_target,
                        'new_target': amount,
                        'timestamp': datetime.now().isoformat()
                    })
        except Exception as e:
            self.logger.error(f"Error setting profit goal: {e}")
    
    def _handle_set_daily_target(self, payload):
        """Handle set daily profit target command."""
        try:
            amount_str = payload.get('amount', '')
            amount = self._parse_money_amount(amount_str)
            if amount:
                self.daily_profit_target = amount
                self.logger.info(f"📅 Daily profit target set: ${amount:,.0f}")
                
                if self.event_bus:
                    self.event_bus.publish('trading.goal.daily.updated', {
                        'daily_target': amount,
                        'timestamp': datetime.now().isoformat()
                    })
        except Exception as e:
            self.logger.error(f"Error setting daily target: {e}")
    
    def _handle_plan_acquire(self, payload):
        """Handle acquire asset command - add to trading plan."""
        try:
            asset = payload.get('asset', '').upper()
            self.logger.info(f"📈 Adding to acquisition plan: {asset}")
            
            # Add to acquisition targets
            if not hasattr(self, 'acquisition_targets'):
                self.acquisition_targets = []
            if asset not in self.acquisition_targets:
                self.acquisition_targets.append(asset)
            
            if self.event_bus:
                self.event_bus.publish('trading.plan.updated', {
                    'action': 'acquire',
                    'asset': asset,
                    'targets': self.acquisition_targets,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Error updating acquisition plan: {e}")
    
    def _handle_plan_sell(self, payload):
        """Handle sell asset command - add to sell plan."""
        try:
            asset = payload.get('asset', '').upper()
            self.logger.info(f"📉 Adding to sell plan: {asset}")
            
            # Add to sell targets
            if not hasattr(self, 'sell_targets'):
                self.sell_targets = []
            if asset not in self.sell_targets:
                self.sell_targets.append(asset)
            
            if self.event_bus:
                self.event_bus.publish('trading.plan.updated', {
                    'action': 'sell',
                    'asset': asset,
                    'targets': self.sell_targets,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Error updating sell plan: {e}")
    
    def _handle_plan_update(self, payload):
        """Handle general trading plan update."""
        try:
            instruction = payload.get('instruction', '')
            self.logger.info(f"📝 Trading plan instruction: {instruction}")
            
            # Store instruction for AI processing
            if not hasattr(self, 'plan_instructions'):
                self.plan_instructions = []
            self.plan_instructions.append({
                'instruction': instruction,
                'timestamp': datetime.now().isoformat()
            })
            
            if self.event_bus:
                self.event_bus.publish('trading.plan.instruction.added', {
                    'instruction': instruction,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Error updating trading plan: {e}")
    
    def _handle_plan_get(self, payload):
        """Handle get current trading plan request."""
        try:
            plan = {
                'profit_target': self.profit_target,
                'current_profit': self.current_profit,
                'daily_target': getattr(self, 'daily_profit_target', 50_000_000),
                'acquisition_targets': getattr(self, 'acquisition_targets', []),
                'sell_targets': getattr(self, 'sell_targets', []),
                'predator_mode': getattr(self, 'predator_mode', False),
                'auto_trading': getattr(self, 'auto_trading_enabled', False),
                'focus_market': getattr(self, 'focus_market', 'all'),
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"📋 Current trading plan requested")
            
            if self.event_bus:
                self.event_bus.publish('trading.plan.current', plan)
        except Exception as e:
            self.logger.error(f"Error getting trading plan: {e}")
    
    def _handle_focus_market(self, payload):
        """Handle focus on specific market command."""
        try:
            market = payload.get('market', 'all').lower()
            self.focus_market = market
            self.logger.info(f"🎯 Focus market set: {market}")
            
            if self.event_bus:
                self.event_bus.publish('trading.focus.updated', {
                    'market': market,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Error setting focus market: {e}")
    
    def _handle_analyze_asset(self, payload):
        """Handle analyze asset request."""
        try:
            symbol = payload.get('symbol', '').upper()
            self.logger.info(f"🔍 Analyzing asset: {symbol}")
            
            # Request analysis from trading intelligence
            if self.event_bus:
                self.event_bus.publish('trading.analysis.request', {
                    'symbol': symbol,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Error analyzing asset: {e}")
    
    def _handle_predator_enable(self, payload):
        """Enable predator/aggressive trading mode."""
        try:
            self.predator_mode = True
            self.logger.info("🐆 PREDATOR MODE ENABLED - Aggressive trading activated")
            
            if self.event_bus:
                self.event_bus.publish('trading.mode.predator', {
                    'enabled': True,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Error enabling predator mode: {e}")
    
    def _handle_predator_disable(self, payload):
        """Disable predator/aggressive trading mode."""
        try:
            self.predator_mode = False
            self.logger.info("🐆 Predator mode disabled - Normal trading resumed")
            
            if self.event_bus:
                self.event_bus.publish('trading.mode.predator', {
                    'enabled': False,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Error disabling predator mode: {e}")
    
    def _handle_auto_trading_start(self, payload):
        """Start auto trading."""
        try:
            self.auto_trading_enabled = True
            self.logger.info("🤖 AUTO TRADING STARTED")
            
            if self.event_bus:
                self.event_bus.publish('trading.auto.started', {
                    'enabled': True,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Error starting auto trading: {e}")
    
    def _handle_auto_trading_stop(self, payload):
        """Stop auto trading."""
        try:
            self.auto_trading_enabled = False
            self.logger.info("🤖 Auto trading stopped")
            
            if self.event_bus:
                self.event_bus.publish('trading.auto.stopped', {
                    'enabled': False,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Error stopping auto trading: {e}")
    
    def _handle_autonomous_decision(self, data: dict):
        """Execute autonomous trading decisions from the AI orchestrator."""
        if not isinstance(data, dict):
            return
        action = data.get('action', 'hold')
        if action == 'hold':
            return
        symbol = data.get('symbol', '')
        amount = data.get('amount', 0)
        self.logger.info(f"Autonomous decision: {action} {symbol} amount={amount}")
        try:
            self.event_bus.publish("trading.execute", {
                "action": action,
                "symbol": symbol,
                "amount": amount,
                "source": "autonomous_orchestrator",
                "timestamp": time.time()
            })
        except Exception as e:
            self.logger.error(f"Failed to execute autonomous decision: {e}")

    def _parse_money_amount(self, amount_str: str) -> int:
        """Parse money amount from string like '1 billion', '50 million', '2 trillion'."""
        try:
            amount_str = str(amount_str).lower().replace(',', '').replace('$', '').strip()
            
            multipliers = {
                'trillion': 1_000_000_000_000,
                't': 1_000_000_000_000,
                'billion': 1_000_000_000,
                'b': 1_000_000_000,
                'million': 1_000_000,
                'm': 1_000_000,
                'thousand': 1_000,
                'k': 1_000,
            }
            
            for word, mult in multipliers.items():
                if word in amount_str:
                    num_str = amount_str.replace(word, '').strip()
                    num = float(num_str) if num_str else 1
                    return int(num * mult)
            
            # Try to parse as plain number
            return int(float(amount_str))
        except Exception:
            return 0
