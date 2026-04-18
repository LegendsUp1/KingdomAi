# core/ai_trading_system.py
import asyncio
import logging
import os
import time
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from sklearn.ensemble import IsolationForest
from deap import base, creator, tools, algorithms  # For genetic algorithm
import matplotlib.pyplot as plt
import sqlite3
import json
from pathlib import Path


def _is_wsl2() -> bool:
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except Exception:
        return False
# Security note: The pickle module is used for model serialization. 
# In a production environment, consider using a more secure serialization method
# such as dill or cloudpickle, or implement proper validation before loading
# pickled data to mitigate potential security risks.
import pickle
from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

# Define fitness function for genetic algorithm
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", list, fitness=creator.FitnessMax)

class AITradingSystem(BaseComponent):
    """AI-driven trading strategy system with self-formulating logic.
    
    🦁 PREDATOR MODE: After 24h learning, becomes AGGRESSIVELY hunting profits!
    """

    def __init__(self, event_bus, config: Optional[Dict[str, Any]] = None):
        super().__init__(event_bus=event_bus, config=config or {})
        self.strategies: Dict[str, Any] = {}
        # Portable path: always use ~/.kingdom_ai/ for SQLite (avoids NTFS locking issues)
        _db_dir = Path.home() / '.kingdom_ai'
        _db_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(_db_dir / 'strategies.db')
        self.db_conn = sqlite3.connect(db_path)
        self.db_conn.execute("PRAGMA journal_mode=WAL")
        self.db_conn.execute("PRAGMA synchronous=NORMAL")
        self._create_db_tables()
        self.historical_data: pd.DataFrame = pd.DataFrame()
        self._ccxt_exchange = None
        
        # 🦁 PREDATOR MODE tracking
        self._init_timestamp = time.time()
        self._predator_mode_active = False
        self._analysis_ready_for_predator = bool(self.config.get("analysis_ready_for_predator", False))
        self._trades_executed = 0
        self._profits_captured = 0.0
        
        # LEARNING PHASE thresholds (conservative first 24h)
        self._learning_position_size = 0.1   # 10% position size during learning
        self._learning_threshold = 0.5       # Higher threshold during learning
        
        # 🦁 PREDATOR MODE thresholds (AGGRESSIVE after 24h)
        self._predator_position_size = 0.3   # 30% position size - HUNT BIG!
        self._predator_threshold = 0.2       # Lower threshold - HUNT EVERYTHING!
        
        # Current active thresholds
        self.position_size = self._learning_position_size
        self.signal_threshold = self._learning_threshold

    async def initialize(self) -> bool:
        """Initialize the AI trading system."""
        try:
            logger.info("Initializing AITradingSystem...")
            await self._load_historical_data()
            await self._load_strategies_from_db()
            if self.event_bus:
                await self.event_bus.subscribe_sync("market.data_update", self._update_market_data)
                await self.event_bus.subscribe_sync("strategy.create", self._create_strategy)
                await self.event_bus.subscribe_sync("strategy.backtest", self._backtest_strategy)
                await self.event_bus.subscribe_sync("strategy.optimize", self._optimize_strategy)
                await self.event_bus.subscribe_sync("strategy.execute", self._execute_strategy)
                # KAIG Intelligence Bridge — THREE TARGETS + rebrand resilience
                await self.event_bus.subscribe_sync("kaig.intel.trading.directive", self._on_kaig_directive)
                await self.event_bus.subscribe_sync("kaig.identity.changed", self._on_identity_changed)
                await self.event_bus.subscribe_sync("ai.autotrade.analysis.ready", self._on_analysis_ready)
            logger.info("AITradingSystem initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AITradingSystem: {e}")
            return False

    def _on_kaig_directive(self, event_data):
        """Receive KAIG directive — 3 targets every strategy must know."""
        if isinstance(event_data, dict):
            self._kaig_directive = event_data
            floor = event_data.get('kaig_survival_floor', {})
            if not floor.get('survival_met', False):
                # Force aggressive mode if survival floor not met
                if not self._predator_mode_active:
                    logger.info("KAIG SURVIVAL NOT MET — forcing early PREDATOR MODE")
                    self._activate_predator_mode()

    def _on_identity_changed(self, event_data):
        """Handle token rebrand — all AI trading strategies and profits preserved.
        Balances tracked by wallet address, not token name. Zero loss."""
        if isinstance(event_data, dict):
            logger.warning(
                "AITradingSystem: TOKEN REBRANDED %s → %s. All strategies and profits preserved.",
                event_data.get("old_ticker", "?"),
                event_data.get("new_ticker", "?"))

    def _on_analysis_ready(self, event_data):
        """Receive analysis completion signal for predator-mode transition."""
        if isinstance(event_data, dict):
            self._analysis_ready_for_predator = bool(event_data.get("ready", True))

    async def _load_historical_data(self) -> None:
        """Load historical market data via ccxt (falls back to DB cache)."""
        try:
            import ccxt
            exchange_id = self.config.get("exchange", "binance")
            symbol = self.config.get("symbol", "BTC/USDT")
            timeframe = self.config.get("timeframe", "1h")
            limit = int(self.config.get("ohlcv_limit", 1000))

            if self._ccxt_exchange is None:
                exchange_cls = getattr(ccxt, exchange_id, None)
                if exchange_cls is None:
                    raise ValueError(f"Exchange {exchange_id} not found in ccxt")
                self._ccxt_exchange = exchange_cls({"enableRateLimit": True})

            ohlcv = self._ccxt_exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if ohlcv:
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "price", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("timestamp", inplace=True)
                self.historical_data = df
                logger.info(f"Loaded {len(df)} candles for {symbol} from {exchange_id}")
                return
        except Exception as e:
            logger.warning(f"ccxt fetch failed ({e}), trying DB cache")

        try:
            cur = self.db_conn.execute(
                "SELECT timestamp, price, volume FROM market_data ORDER BY timestamp DESC LIMIT 1000"
            )
            rows = cur.fetchall()
            if rows:
                df = pd.DataFrame(rows, columns=["timestamp", "price", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)
                self.historical_data = df.sort_index()
                logger.info(f"Loaded {len(df)} cached records from DB")
                return
        except Exception:
            pass

        logger.warning("No historical data available — starting with empty DataFrame")
        self.historical_data = pd.DataFrame(columns=["price", "volume"])

    async def _update_market_data(self, event_data: Dict[str, Any]) -> None:
        """Update market data in real-time."""
        try:
            new_data = pd.DataFrame([event_data], index=[pd.to_datetime(event_data["timestamp"])])
            self.historical_data = pd.concat([self.historical_data, new_data])
            await self._update_active_strategies(new_data)
            logger.debug("Market data updated")
        except Exception as e:
            logger.error(f"Failed to update market data: {e}")
            
    async def _update_active_strategies(self, new_data: pd.DataFrame) -> None:
        """Update active strategies with new market data."""
        for strategy_id, strategy in self.strategies.items():
            if strategy.get("active", False):
                await self._execute_strategy({"strategy_id": strategy_id, "new_data": new_data})




    def initialize_sync(self):


        """Synchronous version of initialize"""


        return True

    async def _create_strategy(self, event_data: Dict[str, Any]) -> None:
        """Create a new AI-generated trading strategy."""
        try:
            strategy_id = event_data.get("strategy_id", f"strategy_{len(self.strategies)}")
            strategy_type = event_data.get("type", "anomaly_detection")
            
            if strategy_id in self.strategies:
                logger.warning(f"Strategy {strategy_id} already exists, updating instead")
            
            # Basic strategy types (expandable)
            if strategy_type == "anomaly_detection":
                # Isolation Forest for anomaly detection
                model = IsolationForest(contamination=0.01, random_state=42)
                features = self.historical_data[["price", "volume"]]
                model.fit(features)
                
                self.strategies[strategy_id] = {
                    "id": strategy_id,
                    "type": strategy_type,
                    "model": model,
                    "params": {"threshold": 0.5, "position_size": 0.1},
                    "performance": {},
                    "active": False,
                    "created_at": pd.Timestamp.now()
                }
            elif strategy_type == "reinforcement_learning":
                lr = event_data.get("learning_rate", 0.001)
                gamma = event_data.get("gamma", 0.99)
                n_features = 2
                if not self.historical_data.empty:
                    n_features = len([c for c in self.historical_data.columns if c in ("price", "volume", "open", "high", "low")])
                n_actions = 3  # hold, buy, sell
                q_table = np.zeros((100, n_actions))  # discretized state space
                self.strategies[strategy_id] = {
                    "id": strategy_id,
                    "type": "reinforcement_learning",
                    "params": {"learning_rate": lr, "gamma": gamma, "epsilon": 1.0, "epsilon_decay": 0.995, "epsilon_min": 0.01},
                    "q_table": q_table,
                    "n_features": n_features,
                    "n_actions": n_actions,
                    "performance": {},
                    "active": False,
                    "created_at": pd.Timestamp.now(),
                    "episode": 0,
                }
            else:
                logger.error(f"Unknown strategy type: {strategy_type}")
                return
                
            # Save strategy to database
            await self._save_strategy_to_db(strategy_id)
            
            # Notify about strategy creation
            await self.event_bus.publish("strategy.created", {
                "strategy_id": strategy_id,
                "type": strategy_type
            })
            
            logger.info(f"Created strategy: {strategy_id} (type: {strategy_type})")
        except Exception as e:
            logger.error(f"Failed to create strategy: {e}")

    async def _backtest_strategy(self, event_data: Dict[str, Any]) -> None:
        """Backtest a strategy using historical data."""
        strategy_id = event_data["strategy_id"]
        strategy = self.strategies.get(strategy_id)
        
        if not strategy:
            logger.error(f"Strategy {strategy_id} not found")
            return

        try:
            logger.info(f"Starting backtest for strategy {strategy_id}")
            
            # Prepare data
            features = self.historical_data[["price", "volume"]]
            
            # Generate signals based on strategy type
            if strategy["type"] == "anomaly_detection":
                # Anomaly detection approach
                model = strategy["model"]
                anomalies = model.predict(features)
                signals = np.where(anomalies == -1, 1, 0)  # Buy on anomalies
            elif strategy["type"] == "reinforcement_learning":
                q_table = strategy.get("q_table")
                params = strategy["params"]
                lr = params["learning_rate"]
                gamma = params["gamma"]
                eps = params.get("epsilon", 0.1)
                eps_decay = params.get("epsilon_decay", 0.995)
                eps_min = params.get("epsilon_min", 0.01)
                n_actions = strategy.get("n_actions", 3)
                n_bins = q_table.shape[0] if q_table is not None else 100

                prices = features["price"].values
                pct = np.diff(prices) / (prices[:-1] + 1e-9)
                bins = np.linspace(pct.min() - 1e-9, pct.max() + 1e-9, n_bins + 1)
                states = np.digitize(pct, bins) - 1
                states = np.clip(states, 0, n_bins - 1)

                signals = np.zeros(len(features))
                for i in range(len(states)):
                    s = states[i]
                    if np.random.random() < eps:
                        action = np.random.randint(n_actions)
                    else:
                        action = int(np.argmax(q_table[s]))
                    signals[i + 1] = action - 1  # -1=sell, 0=hold, 1=buy

                    reward = (prices[i + 1] - prices[i]) / (prices[i] + 1e-9) * (action - 1)
                    s_next = states[min(i + 1, len(states) - 1)]
                    q_table[s, action] += lr * (reward + gamma * np.max(q_table[s_next]) - q_table[s, action])
                    eps = max(eps_min, eps * eps_decay)

                strategy["q_table"] = q_table
                strategy["params"]["epsilon"] = eps
                strategy["episode"] = strategy.get("episode", 0) + 1
            else:
                logger.error(f"Unsupported strategy type for backtesting: {strategy['type']}")
                return

            # Calculate returns
            price_series = self.historical_data["price"]
            returns = price_series.pct_change().shift(-1)  # Next period returns
            strategy_returns = returns * signals  # Apply strategy signals
            
            # Handle NaN values
            strategy_returns = strategy_returns.fillna(0)
            
            # Calculate cumulative returns
            cumulative_returns = (1 + strategy_returns).cumprod()
            
            # Calculate performance metrics
            total_return = cumulative_returns.iloc[-1] - 1
            sharpe_ratio = np.mean(strategy_returns) / np.std(strategy_returns) * np.sqrt(252) if np.std(strategy_returns) > 0 else 0
            max_drawdown = (cumulative_returns.cummax() - cumulative_returns) / cumulative_returns.cummax()
            max_drawdown = max_drawdown.max()
            win_rate = np.sum(strategy_returns > 0) / np.sum(signals != 0) if np.sum(signals != 0) > 0 else 0
            
            # Save performance metrics
            strategy["performance"] = {
                "total_return": float(total_return),
                "sharpe_ratio": float(sharpe_ratio),
                "max_drawdown": float(max_drawdown),
                "win_rate": float(win_rate),
                "backtest_date": pd.Timestamp.now().isoformat()
            }

            # Visualize performance
            await self._visualize_performance(strategy_id, cumulative_returns)
            
            # Save updated strategy
            await self._save_strategy_to_db(strategy_id)
            
            # Publish backtest results
            await self.event_bus.publish("strategy.backtested", {
                "strategy_id": strategy_id,
                "performance": strategy["performance"]
            })
            
            logger.info(f"Backtest completed for {strategy_id}: Return={total_return:.2f}, Sharpe={sharpe_ratio:.2f}")
        except Exception as e:
            logger.error(f"Backtest failed for {strategy_id}: {e}")

    async def _optimize_strategy(self, event_data: Dict[str, Any]) -> None:
        """Optimize strategy parameters using genetic algorithm."""
        strategy_id = event_data["strategy_id"]
        strategy = self.strategies.get(strategy_id)
        
        if not strategy:
            logger.error(f"Strategy {strategy_id} not found")
            return

        try:
            logger.info(f"Starting optimization for strategy {strategy_id}")
            
            # Define evaluation function for genetic algorithm
            def evaluate(individual):
                # Apply parameters
                threshold = individual[0]
                position_size = individual[1]
                
                # Generate signals based on strategy type
                features = self.historical_data[["price", "volume"]]
                
                if strategy["type"] == "anomaly_detection":
                    anomalies = strategy["model"].predict(features)
                    # Apply threshold - only trade if price > threshold
                    price_above_threshold = self.historical_data["price"] > threshold
                    signals = np.where((anomalies == -1) & price_above_threshold, position_size, 0)
                else:
                    # Use real indicator-based signals for other strategies
                    # Calculate RSI, MACD, Bollinger Bands as fallback
                    try:
                        import pandas as pd
                        prices = self.historical_data["price"].values if hasattr(self.historical_data, "price") else features
                        if len(prices) >= 14:
                            # Calculate RSI
                            delta = pd.Series(prices).diff()
                            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                            rs = gain / loss
                            rsi = 100 - (100 / (1 + rs))
                            current_rsi = rsi.iloc[-1] if not rsi.empty else 50
                            
                            # Generate signals based on RSI
                            if current_rsi < 30:  # Oversold - buy signal
                                signals = np.full(len(features), position_size * 0.5)
                            elif current_rsi > 70:  # Overbought - sell signal
                                signals = np.full(len(features), -position_size * 0.5)
                            else:
                                signals = np.zeros(len(features))
                        else:
                            signals = np.zeros(len(features))
                    except ImportError:
                        self.logger.warning("pandas not available for indicator calculation")
                        signals = np.zeros(len(features))
                    except Exception as e:
                        self.logger.debug(f"Indicator calculation failed: {e}")
                        signals = np.zeros(len(features))
                
                # Calculate returns
                returns = self.historical_data["price"].pct_change().shift(-1)
                strategy_returns = returns * signals
                
                # Calculate Sharpe ratio (fitness)
                sharpe = np.mean(strategy_returns) / np.std(strategy_returns) * np.sqrt(252) if np.std(strategy_returns) > 0 else -1
                
                # Avoid NaN/Inf
                if np.isnan(sharpe) or np.isinf(sharpe):
                    sharpe = -1
                    
                return (sharpe,)
            
            # Setup genetic algorithm
            toolbox = base.Toolbox()
            
            # Parameter ranges - customize based on strategy
            price_range = [self.historical_data["price"].min(), self.historical_data["price"].max()]
            
            # Register genetic algorithm components
            toolbox.register("attr_threshold", np.random.uniform, price_range[0], price_range[1])
            toolbox.register("attr_position", np.random.uniform, 0.01, 1.0)  # Position size 1-100%
            toolbox.register("individual", tools.initCycle, creator.Individual, 
                            (toolbox.attr_threshold, toolbox.attr_position), n=1)
            toolbox.register("population", tools.initRepeat, list, toolbox.individual)
            toolbox.register("evaluate", evaluate)
            toolbox.register("mate", tools.cxBlend, alpha=0.5)
            toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=1, indpb=0.2)
            toolbox.register("select", tools.selTournament, tournsize=3)
            
            # Create initial population
            pop = toolbox.population(n=50)
            hof = tools.HallOfFame(1)
            
            # Track stats
            stats = tools.Statistics(lambda ind: ind.fitness.values)
            stats.register("avg", np.mean)
            stats.register("max", np.max)
            
            # Run genetic algorithm
            _, log = algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.2, 
                                         ngen=10, stats=stats, halloffame=hof, verbose=False)
            
            # Get best parameters
            best_params = {
                "threshold": float(hof[0][0]),
                "position_size": float(hof[0][1])
            }
            
            # Update strategy parameters
            strategy["params"] = best_params
            strategy["performance"]["optimization_date"] = pd.Timestamp.now().isoformat()
            
            # Save updated strategy
            await self._save_strategy_to_db(strategy_id)
            
            # Publish optimization results
            await self.event_bus.publish("strategy.optimized", {
                "strategy_id": strategy_id,
                "best_params": best_params,
                "best_fitness": float(hof[0].fitness.values[0])
            })
            
            logger.info(f"Optimized strategy {strategy_id}: threshold={best_params['threshold']:.2f}, position_size={best_params['position_size']:.2f}")
        except Exception as e:
            logger.error(f"Optimization failed for {strategy_id}: {e}")

    def _check_predator_transition(self):
        """🦁 Activate PREDATOR MODE when analysis is ready (not 24h clock)."""
        if self._predator_mode_active:
            return

        if self._analysis_ready_for_predator:
            self._activate_predator_mode()
    
    def _activate_predator_mode(self):
        """🦁 ACTIVATE PREDATOR MODE - Execute trades aggressively!"""
        logger.info("🦁🦁🦁 AI TRADING SYSTEM - PREDATOR MODE ACTIVATING 🦁🦁🦁")
        logger.info("HUNTING for profits — KAIG TARGETS: "
                   "1) $26K survival floor 2) 1 KAIG > highest ATH ever 3) $2T ultimate")
        
        self._predator_mode_active = True
        
        # Switch to PREDATOR thresholds
        self.position_size = self._predator_position_size  # 30% positions
        self.signal_threshold = self._predator_threshold   # Lower threshold
        
        logger.info(f"🎯 PREDATOR position_size: {self.position_size}")
        logger.info(f"🔥 PREDATOR signal_threshold: {self.signal_threshold}")
        
        # Update all existing strategies to be more aggressive
        for strategy_id, strategy in self.strategies.items():
            if "params" in strategy:
                strategy["params"]["position_size"] = self.position_size
                strategy["params"]["threshold"] = self.signal_threshold
                logger.info(f"🦁 Strategy {strategy_id} upgraded to PREDATOR mode")
    
    def is_predator_mode(self) -> bool:
        """Check if PREDATOR MODE is active."""
        return self._predator_mode_active

    async def _execute_strategy(self, event_data: Dict[str, Any]) -> None:
        """Execute a strategy in real-time.
        
        🦁 PREDATOR MODE: Executes more aggressively after 24h!
        """
        # 🦁 Check for PREDATOR MODE transition
        self._check_predator_transition()
        
        strategy_id = event_data["strategy_id"]
        strategy = self.strategies.get(strategy_id)
        new_data = event_data.get("new_data")
        
        if not strategy:
            logger.error(f"Strategy {strategy_id} not found")
            return

        try:
            # Mark as active if not already
            if not strategy.get("active", False) and new_data is None:
                strategy["active"] = True
                await self._save_strategy_to_db(strategy_id)
                logger.info(f"Strategy {strategy_id} is now active")
                await self.event_bus.publish("strategy.status_changed", {
                    "strategy_id": strategy_id, 
                    "status": "active",
                    "predator_mode": self._predator_mode_active
                })
                return
            
            # Exit if we're only activating or if no new data
            if new_data is None:
                return
            
            # Real-time execution logic
            features = new_data[["price", "volume"]]
            
            # 🦁 PREDATOR MODE: Use aggressive thresholds
            threshold = self.signal_threshold if self._predator_mode_active else strategy["params"]["threshold"]
            position_size = self.position_size if self._predator_mode_active else strategy["params"]["position_size"]
            
            # Generate signals based on strategy type
            signal = 0
            if strategy["type"] == "anomaly_detection":
                # Apply model to new data
                anomaly = strategy["model"].predict(features)[0]
                
                # 🦁 PREDATOR MODE: Lower threshold = more trades!
                if anomaly == -1 and features["price"].iloc[0] > threshold:
                    signal = position_size
                    if self._predator_mode_active:
                        logger.info(f"🦁 PREDATOR STRIKE: Anomaly detected for {strategy_id}!")
            
            # If we have a signal, create a trade
            if signal != 0:
                trade = {
                    "strategy_id": strategy_id,
                    "timestamp": pd.Timestamp.now().isoformat(),
                    "action": "buy" if signal > 0 else "sell",
                    "amount": abs(signal),
                    "price": float(features["price"].iloc[0]),
                    "symbol": "BTC/USD",  # Example symbol
                    "predator_mode": self._predator_mode_active
                }
                
                # Track executions
                self._trades_executed += 1
                
                # Publish trade event
                await self.event_bus.publish("strategy.trade_executed", trade)
                
                if self._predator_mode_active:
                    logger.info(f"🦁 PREDATOR EXECUTED: {trade['action']} {trade['amount']:.2f} at ${trade['price']:.2f}")
                else:
                    logger.info(f"Strategy {strategy_id} executed trade: {trade['action']} {trade['amount']} at {trade['price']}")
        except Exception as e:
            logger.error(f"Execution failed for {strategy_id}: {e}")
    
    async def _visualize_performance(self, strategy_id: str, cumulative_returns: pd.Series) -> None:
        """Visualize strategy performance."""
        try:
            # Create performance chart
            plt.figure(figsize=(10, 6))
            cumulative_returns.plot()
            plt.title(f"Strategy {strategy_id} Cumulative Returns")
            plt.xlabel("Time")
            plt.ylabel("Cumulative Return")
            plt.grid(True)
            
            # Save to file
            file_path = f"strategy_{strategy_id}_performance.png"
            plt.savefig(file_path)
            plt.close()
            
            # Publish visualization event with file path
            await self.event_bus.publish("strategy.visualization", {
                "strategy_id": strategy_id,
                "file_path": file_path
            })
            logger.info(f"Performance visualization saved for {strategy_id}")
        except Exception as e:
            logger.error(f"Visualization failed for {strategy_id}: {e}")

    def _create_db_tables(self) -> None:
        """Create database tables for strategy persistence."""
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    model BLOB,
                    params TEXT,
                    performance TEXT,
                    active INTEGER,
                    created_at TEXT
                )
            """)
            self.db_conn.commit()
            logger.debug("Database tables created")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")

    async def _save_strategy_to_db(self, strategy_id: str) -> None:
        """Save strategy to database."""
        try:
            strategy = self.strategies[strategy_id]
            cursor = self.db_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO strategies (id, type, model, params, performance, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_id,
                strategy["type"],
                pickle.dumps(strategy.get("model", None)),
                json.dumps(strategy["params"]),
                json.dumps(strategy["performance"]),
                1 if strategy.get("active", False) else 0,
                strategy["created_at"].isoformat() if isinstance(strategy["created_at"], pd.Timestamp) else strategy["created_at"]
            ))
            self.db_conn.commit()
            logger.debug(f"Strategy {strategy_id} saved to database")
        except Exception as e:
            logger.error(f"Failed to save strategy {strategy_id} to database: {e}")

    async def _load_strategies_from_db(self) -> None:
        """Load all strategies from database."""
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT id, type, model, params, performance, active, created_at FROM strategies")
            for row in cursor.fetchall():
                strategy_id, type_, model_blob, params_json, performance_json, active, created_at = row
                self.strategies[strategy_id] = {
                    "id": strategy_id,
                    "type": type_,
                    "model": pickle.loads(model_blob) if model_blob else None,
                    "params": json.loads(params_json),
                    "performance": json.loads(performance_json),
                    "active": bool(active),
                    "created_at": created_at
                }
            logger.info(f"Loaded {len(self.strategies)} strategies from database")
        except Exception as e:
            logger.error(f"Failed to load strategies from database: {e}")

    async def shutdown(self) -> bool:
        """Shutdown the AI trading system."""
        try:
            # Deactivate all strategies
            for strategy_id in self.strategies:
                self.strategies[strategy_id]["active"] = False
                await self._save_strategy_to_db(strategy_id)
            
            # Close database connection
            if self.db_conn:
                self.db_conn.close()
                
            logger.info("AITradingSystem shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Error during AITradingSystem shutdown: {e}")
            return False

# Example usage
if __name__ == "__main__":
    from core.event_bus import EventBus
    
    async def test_ai_trading():
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        
        # Create event bus and AI system
        event_bus = EventBus()
        ai_system = AITradingSystem(event_bus=event_bus)
        
        # Initialize the system
        await ai_system.initialize()
        
        # Create a strategy
        await event_bus.publish("strategy.create", {
            "strategy_id": "anomaly_strategy",
            "type": "anomaly_detection"
        })
        
        # Backtest the strategy
        await event_bus.publish("strategy.backtest", {
            "strategy_id": "anomaly_strategy"
        })
        
        # Optimize the strategy
        await event_bus.publish("strategy.optimize", {
            "strategy_id": "anomaly_strategy"
        })
        
        # Execute the strategy
        await event_bus.publish("strategy.execute", {
            "strategy_id": "anomaly_strategy"
        })
        
        # Process events
        await asyncio.sleep(5)
        
        # Shutdown
        await ai_system.shutdown()

    # Run the test
    asyncio.run(test_ai_trading())
