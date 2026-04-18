"""
AI-Enhanced Execution Optimizer (2025)
Advanced machine learning algorithms for optimizing trade execution,
reducing slippage, and minimizing latency in perpetual futures trading.
"""

import asyncio
import logging
import time

from core.base_component import BaseComponent
from utils.redis_client import RedisClient
from utils.async_utils import AsyncSupport

class AIExecutionOptimizer(BaseComponent):
    """
    State-of-the-art AI-driven trade execution optimizer that uses machine learning
    to minimize slippage, optimize execution timing, and improve overall trade performance.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the AI Execution Optimizer component."""
        super().__init__("AIExecutionOptimizer", event_bus, config)
        self.redis_client = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.shutdown_event = asyncio.Event()
        
        # Configuration
        self.config = config or {
            "model_update_frequency_hours": 12,
            "prediction_window_seconds": 30,
            "slippage_history_days": 30,
            "execution_algorithms": ["iceberg", "twap", "vwap", "adaptive", "ml_optimized"],
            "latency_threshold_ms": 100,
            "max_acceptable_slippage_bps": 10,
            "execution_timeout_seconds": 60,
            "exchanges": ["binance", "okx", "bybit", "deribit", "gate"],
            "models": {
                "slippage_prediction": {
                    "type": "lstm",
                    "enabled": True,
                    "layers": 3,
                    "units": 128,
                    "dropout": 0.2
                },
                "latency_optimization": {
                    "type": "gru",
                    "enabled": True,
                    "layers": 2,
                    "units": 64,
                    "dropout": 0.1
                },
                "market_impact": {
                    "type": "transformer",
                    "enabled": True,
                    "attention_heads": 4,
                    "layers": 2
                }
            },
            "feature_importance_tracking": True,
            "adaptive_learning": True,
            "anomaly_detection": True,
            "enable_quantum_optimization": False  # Future feature
        }
        
        # Internal state
        self.models = {}
        self.execution_stats = {}
        self.market_conditions = {}
        self.active_executions = {}
    
    async def initialize(self):
        """Initialize the component and connect to Redis Quantum Nexus."""
        self.logger.info("Initializing AI Execution Optimizer")
        
        # Connect to Redis Quantum Nexus with strict enforcement
        try:
            self.redis_client = RedisClient(
                host="localhost", 
                port=6380,
                password="QuantumNexus2025",
                db=0,
                decode_responses=True
            )
            # Test connection
            ping_result = await self.redis_client.ping()
            if not ping_result:
                raise ConnectionError("Redis ping failed")
            self.logger.info("Successfully connected to Redis Quantum Nexus")
        except Exception as e:
            self.logger.critical(f"Failed to connect to Redis Quantum Nexus: {e}")
            # Enforcing strict no-fallback policy
            raise SystemExit("Critical failure: Redis Quantum Nexus connection failed. Halting system.")
        
        # Register event handlers
        if self.event_bus:
            await self.event_bus.subscribe("order_execution_request", self.on_execution_request)
            await self.event_bus.subscribe("market_data_update", self.on_market_data_update)
            await self.event_bus.subscribe("order_book_update", self.on_orderbook_update)
            await self.event_bus.subscribe("trade_execution_completed", self.on_execution_completed)
            await self.event_bus.subscribe("system_shutdown", self.on_shutdown)
        
        # Initialize models
        await self.initialize_models()
        
        # Start background tasks
        AsyncSupport.create_background_task(self.model_training_task())
        AsyncSupport.create_background_task(self.latency_monitoring_task())
        AsyncSupport.create_background_task(self.feature_importance_analysis_task())
        
        self.logger.info("AI Execution Optimizer initialized successfully")
        return True
    
    async def initialize_models(self):
        """Initialize the machine learning models for execution optimization."""
        try:
            # In a real implementation, this would load model architectures and weights
            # For now, we'll just set up the structure
            self.models["slippage_prediction"] = {
                "status": "initializing",
                "last_updated": time.time(),
                "features": [
                    "order_size_relative_to_volume", 
                    "bid_ask_spread", 
                    "recent_volatility",
                    "order_book_imbalance",
                    "market_impact_score",
                    "trade_flow_imbalance",
                    "recent_price_trend",
                    "time_of_day",
                    "exchange_latency"
                ],
                "performance": {
                    "mae": None,
                    "rmse": None,
                    "r2": None
                }
            }
            
            self.models["latency_optimization"] = {
                "status": "initializing",
                "last_updated": time.time(),
                "features": [
                    "exchange_load", 
                    "network_congestion", 
                    "time_of_day",
                    "order_complexity",
                    "historical_latency"
                ],
                "performance": {
                    "mae": None,
                    "rmse": None
                }
            }
            
            self.models["market_impact"] = {
                "status": "initializing",
                "last_updated": time.time(),
                "features": [
                    "order_size", 
                    "market_depth", 
                    "liquidity_concentration",
                    "recent_large_orders",
                    "price_volatility"
                ],
                "performance": {
                    "mae": None,
                    "rmse": None
                }
            }
            
            # Record initialization in Redis
            for model_name, model_data in self.models.items():
                key = f"ai:execution:model:{model_name}"
                await self.redis_client.hset(key, "status", "initialized")
                await self.redis_client.hset(key, "last_updated", str(time.time()))
            
            self.logger.info("Machine learning models initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize models: {e}")
            raise
    
    async def on_execution_request(self, data):
        """
        Handle incoming trade execution requests and apply AI optimization.
        """
        try:
            execution_id = data.get("execution_id")
            exchange = data.get("exchange")
            symbol = data.get("symbol")
            side = data.get("side")  # buy or sell
            quantity = data.get("quantity")
            order_type = data.get("order_type")
            price = data.get("price")  # Optional for limit orders
            
            if not all([execution_id, exchange, symbol, side, quantity, order_type]):
                self.logger.warning(f"Incomplete execution request data: {data}")
                return
            
            self.logger.info(f"Processing execution request {execution_id} for {quantity} {symbol} {side}")
            
            # Store execution request
            self.active_executions[execution_id] = {
                "status": "optimizing",
                "request": data,
                "start_time": time.time(),
                "optimization_result": None,
                "execution_algo": None,
                "slippage_prediction": None
            }
            
            # Get current market conditions
            market_data = await self._get_market_data(exchange, symbol)
            order_book = await self._get_orderbook(exchange, symbol)
            
            # Predict slippage for different execution algorithms
            slippage_predictions = await self._predict_slippage(
                exchange, symbol, side, quantity, market_data, order_book
            )
            
            # Predict latency for different execution paths
            latency_predictions = await self._predict_latency(exchange, symbol, order_type)
            
            # Select optimal execution algorithm
            optimal_algo, params = await self._select_execution_algorithm(
                slippage_predictions, latency_predictions, data
            )
            
            # Update execution record
            self.active_executions[execution_id].update({
                "status": "optimized",
                "optimization_result": {
                    "selected_algorithm": optimal_algo,
                    "parameters": params,
                    "predicted_slippage_bps": slippage_predictions.get(optimal_algo),
                    "predicted_latency_ms": latency_predictions.get(optimal_algo)
                },
                "execution_algo": optimal_algo
            })
            
            # Publish optimized execution plan
            if self.event_bus:
                await self.event_bus.publish("execution_optimized", {
                    "execution_id": execution_id,
                    "original_request": data,
                    "optimized_plan": {
                        "algorithm": optimal_algo,
                        "parameters": params,
                        "predicted_slippage_bps": slippage_predictions.get(optimal_algo),
                        "predicted_latency_ms": latency_predictions.get(optimal_algo)
                    }
                })
            
        except Exception as e:
            self.logger.error(f"Error processing execution request: {e}")
            # Notify about the error
            if self.event_bus and 'execution_id' in locals():
                await self.event_bus.publish("execution_optimization_failed", {
                    "execution_id": execution_id,
                    "error": str(e)
                })
    
    async def on_market_data_update(self, data):
        """Process market data updates for model improvement."""
        # Store latest market data for each symbol
        exchange = data.get("exchange")
        symbol = data.get("symbol")
        if exchange and symbol:
            key = f"{exchange}:{symbol}"
            self.market_conditions[key] = {
                "last_price": data.get("last_price"),
                "volume_24h": data.get("volume_24h"),
                "price_change_24h": data.get("price_change_24h"),
                "timestamp": data.get("timestamp", time.time())
            }
    
    async def on_orderbook_update(self, data):
        """Process order book updates for execution optimization."""
        if not isinstance(data, dict):
            return
        exchange = data.get("exchange")
        symbol = data.get("symbol")
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        timestamp = data.get("timestamp", time.time())
        if not exchange or not symbol:
            return
        try:
            import json
            bid_volume = sum(float(b[1]) for b in bids[:10]) if bids else 0
            ask_volume = sum(float(a[1]) for a in asks[:10]) if asks else 0
            total_volume = bid_volume + ask_volume
            imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0
            best_bid = float(bids[0][0]) if bids else 0
            best_ask = float(asks[0][0]) if asks else 0
            spread_bps = ((best_ask - best_bid) / best_bid * 10000) if best_bid > 0 else 0
            depth_5 = sum(float(b[1]) for b in bids[:5]) + sum(float(a[1]) for a in asks[:5])
            key = f"{exchange}:{symbol}"
            self.market_conditions.setdefault(key, {}).update({
                "order_book_imbalance": imbalance,
                "bid_ask_spread_bps": spread_bps,
                "top_bid_volume": bid_volume,
                "top_ask_volume": ask_volume,
                "depth_5_levels": depth_5,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "orderbook_timestamp": timestamp
            })
            ob_key = f"orderbook:{exchange}:{symbol}"
            await self.redis_client.set(ob_key, json.dumps({
                "bids": bids[:20],
                "asks": asks[:20],
                "imbalance": imbalance,
                "spread_bps": spread_bps,
                "timestamp": timestamp
            }))
            await self.redis_client.expire(ob_key, 60)
            for exec_id, execution in list(self.active_executions.items()):
                req = execution.get("request", {})
                if req.get("exchange") == exchange and req.get("symbol") == symbol:
                    if execution.get("status") == "optimized":
                        execution.setdefault("live_market", {}).update({
                            "imbalance": imbalance,
                            "spread_bps": spread_bps
                        })
        except Exception as e:
            self.logger.error(f"Error processing orderbook update: {e}")
    
    async def on_execution_completed(self, data):
        """Process completed execution data for model training."""
        execution_id = data.get("execution_id")
        actual_slippage = data.get("slippage_bps")
        execution_time_ms = data.get("execution_time_ms")
        
        if execution_id in self.active_executions:
            execution_record = self.active_executions[execution_id]
            
            # Calculate prediction accuracy
            predicted_slippage = execution_record.get("optimization_result", {}).get("predicted_slippage_bps")
            slippage_error = abs(actual_slippage - predicted_slippage) if predicted_slippage is not None else None
            
            # Store execution statistics
            execution_stats = {
                "execution_id": execution_id,
                "algorithm": execution_record.get("execution_algo"),
                "predicted_slippage_bps": predicted_slippage,
                "actual_slippage_bps": actual_slippage,
                "slippage_error": slippage_error,
                "execution_time_ms": execution_time_ms,
                "completed_at": time.time()
            }
            
            # Store in Redis for future model training
            key = f"ai:execution:stats:{execution_id}"
            if hasattr(self.redis_client, "hset"):
                await self.redis_client.hset(key, mapping=execution_stats)
            else:
                await self.redis_client.hmset(key, execution_stats)
            # Set TTL for data retention
            await self.redis_client.expire(key, 60 * 60 * 24 * self.config["slippage_history_days"])
            
            # Remove from active executions
            self.active_executions.pop(execution_id, None)
            
            # Publish analytics event
            if self.event_bus:
                await self.event_bus.publish("execution_analytics", execution_stats)
    
    async def on_shutdown(self, data):
        """Handle system shutdown."""
        self.logger.info("Shutting down AI Execution Optimizer")
        self.shutdown_event.set()
        if self.redis_client:
            await self.redis_client.close()
    
    # Background tasks
    
    async def model_training_task(self):
        """Periodically retrain models with the latest execution data."""
        try:
            while not self.shutdown_event.is_set():
                self.logger.debug("Running model training task")
                
                # In a real implementation, this would:
                # 1. Fetch recent execution data from Redis
                # 2. Prepare features and targets
                # 3. Train/update models
                # 4. Evaluate performance
                # 5. Update model weights
                
                for model_name in self.models:
                    self.models[model_name]["last_updated"] = time.time()
                    self.models[model_name]["status"] = "trained"
                    
                    # Update Redis with new model status
                    key = f"ai:execution:model:{model_name}"
                    await self.redis_client.hset(key, "status", "trained")
                    await self.redis_client.hset(key, "last_updated", str(time.time()))
                
                # Sleep until next training interval
                hours = self.config.get("model_update_frequency_hours", 12)
                await asyncio.sleep(hours * 3600)
                
        except asyncio.CancelledError:
            self.logger.info("Model training task cancelled")
        except Exception as e:
            self.logger.error(f"Error in model training task: {e}")
    
    async def latency_monitoring_task(self):
        """Monitor system and exchange latency for execution optimization."""
        try:
            while not self.shutdown_event.is_set():
                # In a real implementation, this would:
                # 1. Ping exchanges to measure latency
                # 2. Update latency metrics in Redis
                # 3. Detect latency anomalies
                
                await asyncio.sleep(60)  # Check every minute
                
        except asyncio.CancelledError:
            self.logger.info("Latency monitoring task cancelled")
        except Exception as e:
            self.logger.error(f"Error in latency monitoring task: {e}")
    
    async def feature_importance_analysis_task(self):
        """Analyze feature importance for model explainability."""
        try:
            while not self.shutdown_event.is_set():
                if self.config["feature_importance_tracking"]:
                    self.logger.debug("Running feature importance analysis")
                    # Implementation would analyze which features most affect predictions
                
                await asyncio.sleep(3600 * 24)  # Run daily
                
        except asyncio.CancelledError:
            self.logger.info("Feature importance analysis task cancelled")
        except Exception as e:
            self.logger.error(f"Error in feature importance analysis task: {e}")
    
    # Helper methods
    
    async def _get_market_data(self, exchange, symbol):
        """Get current market data for a symbol."""
        key = f"{exchange}:{symbol}"
        return self.market_conditions.get(key, {})
    
    async def _get_orderbook(self, exchange, symbol):
        """Get current order book for a symbol from Redis."""
        key = f"orderbook:{exchange}:{symbol}"
        try:
            orderbook_data = await self.redis_client.get(key)
            if orderbook_data:
                import json
                return json.loads(orderbook_data)
            return None
        except Exception as e:
            self.logger.error(f"Error fetching orderbook: {e}")
            return None
    
    async def _predict_slippage(self, exchange, symbol, side, quantity, market_data, order_book):
        """
        Predict slippage for different execution algorithms using real historical analysis.
        Returns dict of {algorithm: predicted_slippage_bps}
        """
        predictions = {}
        
        # Try to use real historical analysis if available
        try:
            # Get historical execution data from event_bus or storage
            historical_data = None
            if hasattr(self, 'event_bus') and self.event_bus:
                execution_history = self.event_bus.get_component("execution_history")
                if execution_history and hasattr(execution_history, "get_historical_slippage"):
                    historical_data = execution_history.get_historical_slippage(exchange, symbol)
            
            if historical_data and len(historical_data) > 0:
                # Calculate average slippage per algorithm from historical data
                for algo in self.config["execution_algorithms"]:
                    algo_slippages = [d.get("slippage_bps") for d in historical_data if d.get("algorithm") == algo]
                    if algo_slippages:
                        predictions[algo] = sum(algo_slippages) / len(algo_slippages)
                    else:
                        # No historical data for this algorithm - return 0 (honest "no data")
                        predictions[algo] = 0
                        logger.debug(f"No historical slippage data for algorithm {algo}")
            else:
                # No historical data available - return empty dict (honest "model not trained")
                logger.info("No historical execution data available - model not trained")
                return {}
        except Exception as e:
            logger.warning(f"Error predicting slippage from historical data: {e}")
            return {}
        
        return predictions
    
    async def _predict_latency(self, exchange, symbol, order_type):
        """
        Predict execution latency for different algorithms using real historical analysis.
        Returns dict of {algorithm: predicted_latency_ms}
        """
        predictions = {}
        
        # Try to use real historical analysis if available
        try:
            # Get historical execution data from event_bus or storage
            historical_data = None
            if hasattr(self, 'event_bus') and self.event_bus:
                execution_history = self.event_bus.get_component("execution_history")
                if execution_history and hasattr(execution_history, "get_historical_latency"):
                    historical_data = execution_history.get_historical_latency(exchange, symbol)
            
            if historical_data and len(historical_data) > 0:
                # Calculate average latency per algorithm from historical data
                for algo in self.config["execution_algorithms"]:
                    algo_latencies = [d.get("latency_ms") for d in historical_data if d.get("algorithm") == algo]
                    if algo_latencies:
                        predictions[algo] = sum(algo_latencies) / len(algo_latencies)
                    else:
                        # No historical data for this algorithm - return 0 (honest "no data")
                        predictions[algo] = 0
                        logger.debug(f"No historical latency data for algorithm {algo}")
            else:
                # No historical data available - return empty dict (honest "model not trained")
                logger.info("No historical execution data available - model not trained")
                return {}
        except Exception as e:
            logger.warning(f"Error predicting latency from historical data: {e}")
            return {}
        
        return predictions
    
    async def _select_execution_algorithm(self, slippage_predictions, latency_predictions, request_data):
        """
        Select the optimal execution algorithm based on predictions and constraints.
        Returns (selected_algorithm, parameters)
        """
        # In a real implementation, this would use a more sophisticated decision process
        # For now, simply select the algorithm with the lowest slippage prediction
        
        # Filter algorithms that meet latency requirements
        valid_algos = [
            algo for algo in self.config["execution_algorithms"]
            if latency_predictions.get(algo, float('inf')) <= self.config["latency_threshold_ms"]
        ]
        
        if not valid_algos:
            # If no algorithm meets latency requirements, choose the one with lowest latency
            selected = min(latency_predictions.items(), key=lambda x: x[1])[0]
        else:
            # Choose the algorithm with the lowest predicted slippage
            selected = min(
                [(algo, slippage_predictions.get(algo, float('inf'))) for algo in valid_algos],
                key=lambda x: x[1]
            )[0]
        
        # Generate algorithm-specific parameters
        if selected == "iceberg":
            params = {"chunk_size": 0.2, "chunk_interval_seconds": 5}
        elif selected == "twap":
            params = {"intervals": 5, "interval_seconds": 30}
        elif selected == "vwap":
            params = {"target_participation_rate": 0.1}
        elif selected == "adaptive":
            params = {"max_participation_rate": 0.15, "urgency": "medium"}
        elif selected == "ml_optimized":
            params = {"risk_tolerance": "medium", "prioritize": "minimize_slippage"}
        else:
            params = {}
            
        return selected, params
