import asyncio
import json
import logging
import time
import sys
from typing import Dict, List, Any

# Import base component and utilities
from core.base_component import BaseComponent
from utils.redis_client import RedisClient
from utils.async_support import AsyncSupport
from utils.event_bus import EventBus

class CrossPlatformArbitrage(BaseComponent):
    """
    Cross-Platform Arbitrage Module for the Kingdom AI Trading System.
    
    This module monitors price discrepancies across multiple exchanges and executes
    arbitrage opportunities when profitable after fees and slippage.
    
    Key features:
    - Real-time price monitoring across exchanges
    - Latency-adjusted price comparisons
    - Automatic opportunity detection and execution
    - Risk-controlled position sizing
    - Cross-exchange order routing
    """
    
    def __init__(self, redis_client: RedisClient, event_bus: EventBus, 
                 async_support: AsyncSupport, config_path: str = "config/arbitrage_config.json"):
        """Initialize the Cross-Platform Arbitrage module."""
        super().__init__(name="CrossPlatformArbitrage")
        
        self.logger = logging.getLogger("CrossPlatformArbitrage")
        self.redis_client = redis_client
        self.event_bus = event_bus
        self.async_support = async_support
        self.config_path = config_path
        self.shutdown_event = asyncio.Event()
        
        # State tracking
        self.active_arbitrages = {}
        self.exchange_status = {}
        self.market_data = {}
        self.latency_metrics = {}
        self.fee_structures = {}
        self.execution_stats = {
            "opportunities_detected": 0,
            "trades_executed": 0,
            "total_profit": 0.0,
            "failed_executions": 0
        }
        
        # Load configuration
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            self.logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            self.logger.error(f"Failed to load config from {self.config_path}: {e}")
            # Use default configuration as fallback
            return {
                "enabled_exchanges": ["binance", "bybit", "okx"],
                "monitored_symbols": ["BTC-USDT", "ETH-USDT", "SOL-USDT"],
                "min_price_difference_percent": 0.1,
                "max_position_size_usd": 10000,
                "max_concurrent_arbitrages": 5,
                "heartbeat_interval": 5,
                "opportunity_scan_interval": 1,
                "market_data_refresh_interval": 0.5,
                "latency_measurement_interval": 60,
                "execution_timeout": 30,
                "risk_control": {
                    "max_drawdown_percent": 5.0,
                    "daily_loss_limit_usd": 1000,
                    "position_size_scaling": 0.8
                }
            }
    
    async def initialize(self) -> bool:
        """Initialize the Cross-Platform Arbitrage module."""
        self.logger.info("Initializing Cross-Platform Arbitrage Module")
        
        # 2026 FIX: Allow degraded operation instead of crash
        if not self.redis_client or not await self.redis_client.is_connected():
            self.logger.warning("⚠️ Redis Quantum Nexus connection unavailable - arbitrage will be limited")
        
        # Load exchange configurations
        for exchange in self.config["enabled_exchanges"]:
            exchange_config = await self._load_exchange_config(exchange)
            if not exchange_config:
                self.logger.warning(f"Could not load configuration for exchange {exchange}")
                continue
                
            # Initialize exchange status tracking
            self.exchange_status[exchange] = {
                "connected": False,
                "last_heartbeat": 0,
                "latency_ms": float('inf'),
                "error_count": 0,
                "active": False
            }
            
            # Initialize fee structure from config
            self.fee_structures[exchange] = exchange_config.get("fees", {
                "maker": 0.001,  # Default 0.1% maker fee
                "taker": 0.002   # Default 0.2% taker fee
            })
            
        # Subscribe to events
        if self.event_bus:
            await self.event_bus.subscribe("market_data_update", self.on_market_data_update)
            await self.event_bus.subscribe("exchange_status", self.on_exchange_status_update)
            await self.event_bus.subscribe("arbitrage_execution_result", self.on_execution_result)
            await self.event_bus.subscribe("risk_parameters_update", self.on_risk_parameters_update)
            await self.event_bus.subscribe("system_shutdown", self.on_shutdown)
        
        # Start background tasks
        if self.async_support:
            self.async_support.create_task(self._task_monitor_opportunities())
            self.async_support.create_task(self._task_measure_latency())
            self.async_support.create_task(self._task_exchange_heartbeat())
            self.async_support.create_task(self._task_cleanup_stale_arbitrages())
        
        self.logger.info("Cross-Platform Arbitrage Module initialized successfully")
        return True
        
    async def _load_exchange_config(self, exchange: str) -> Dict[str, Any]:
        """Load configuration for a specific exchange from Redis."""
        try:
            config_key = f"exchange:config:{exchange}"
            config_data = await self.redis_client.get(config_key)
            
            if config_data:
                return json.loads(config_data)
            else:
                self.logger.warning(f"No configuration found for exchange {exchange} in Redis")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error loading config for exchange {exchange}: {e}")
            return {}
    
    # Event handlers
    
    async def on_market_data_update(self, data):
        """Handle market data updates from exchanges."""
        try:
            exchange = data.get("exchange")
            symbol = data.get("symbol")
            price = data.get("price")
            timestamp = data.get("timestamp", time.time())
            
            if not all([exchange, symbol, price is not None]):
                return
                
            # Update market data cache
            if exchange not in self.market_data:
                self.market_data[exchange] = {}
                
            self.market_data[exchange][symbol] = {
                "price": price,
                "timestamp": timestamp,
                "bid": data.get("bid", price),
                "ask": data.get("ask", price),
                "volume_24h": data.get("volume_24h", 0),
                "updated_at": time.time()
            }
            
            # Check if this update creates an arbitrage opportunity
            await self._check_arbitrage_opportunity(exchange, symbol)
            
        except Exception as e:
            self.logger.error(f"Error processing market data update: {e}")
    
    async def on_exchange_status_update(self, data):
        """Handle exchange status updates."""
        try:
            exchange = data.get("exchange")
            status = data.get("status")
            
            if not exchange or status is None:
                return
                
            if exchange in self.exchange_status:
                self.exchange_status[exchange].update({
                    "connected": status == "connected",
                    "last_heartbeat": time.time() if status == "connected" else self.exchange_status[exchange]["last_heartbeat"],
                    "error_count": 0 if status == "connected" else self.exchange_status[exchange]["error_count"] + 1,
                    "active": status == "connected"
                })
                
                # Log status changes
                if status != "connected" and self.exchange_status[exchange]["active"]:
                    self.logger.warning(f"Exchange {exchange} is no longer active, status: {status}")
                elif status == "connected" and not self.exchange_status[exchange]["active"]:
                    self.logger.info(f"Exchange {exchange} is now active")
            
        except Exception as e:
            self.logger.error(f"Error processing exchange status update: {e}")
    
    async def on_execution_result(self, data):
        """Handle arbitrage execution results."""
        try:
            arbitrage_id = data.get("arbitrage_id")
            success = data.get("success", False)
            profit = data.get("profit", 0.0)
            
            if not arbitrage_id:
                return
                
            # Update execution stats
            if success:
                self.execution_stats["trades_executed"] += 1
                self.execution_stats["total_profit"] += profit
                self.logger.info(f"Successfully executed arbitrage {arbitrage_id} with profit {profit}")
            else:
                self.execution_stats["failed_executions"] += 1
                error = data.get("error", "Unknown error")
                self.logger.warning(f"Failed to execute arbitrage {arbitrage_id}: {error}")
            
            # Remove from active arbitrages
            if arbitrage_id in self.active_arbitrages:
                del self.active_arbitrages[arbitrage_id]
                
            # Store execution result in Redis for analysis
            await self.redis_client.set(
                f"arbitrage:result:{arbitrage_id}", 
                json.dumps({
                    "timestamp": time.time(),
                    "success": success,
                    "profit": profit,
                    "details": data
                })
            )
            
            # Publish summary stats
            await self.redis_client.set(
                "arbitrage:stats",
                json.dumps(self.execution_stats)
            )
            
            # Publish update to event bus for dashboard display
            if self.event_bus:
                await self.event_bus.publish("arbitrage_stats_update", self.execution_stats)
            
        except Exception as e:
            self.logger.error(f"Error processing execution result: {e}")
    
    async def on_risk_parameters_update(self, data):
        """Handle risk parameter updates."""
        try:
            if "risk_control" in data:
                self.config["risk_control"].update(data["risk_control"])
                self.logger.info(f"Updated risk parameters: {self.config['risk_control']}")
                
        except Exception as e:
            self.logger.error(f"Error updating risk parameters: {e}")
    
    async def on_shutdown(self, data):
        """Handle system shutdown."""
        self.logger.info("Shutting down Cross-Platform Arbitrage Module")
        self.shutdown_event.set()
        
        # Cancel all pending arbitrages
        for arb_id in list(self.active_arbitrages.keys()):
            await self._cancel_arbitrage(arb_id, reason="System shutdown")
            
        # Publish final stats
        if self.event_bus:
            await self.event_bus.publish("arbitrage_final_stats", self.execution_stats)
    
    # Background tasks
    
    async def _task_monitor_opportunities(self):
        """Background task to actively monitor for arbitrage opportunities."""
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Only scan if not at max concurrent arbitrages
                    if len(self.active_arbitrages) < self.config["max_concurrent_arbitrages"]:
                        await self._scan_all_opportunities()
                except Exception as e:
                    self.logger.error(f"Error in opportunity monitoring: {e}")
                
                # Wait before next scan
                await asyncio.sleep(self.config["opportunity_scan_interval"])
                
        except asyncio.CancelledError:
            self.logger.info("Opportunity monitoring task cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error in opportunity monitoring: {e}")
    
    async def _task_measure_latency(self):
        """Background task to measure exchange latency."""
        try:
            while not self.shutdown_event.is_set():
                try:
                    for exchange in self.exchange_status:
                        if self.exchange_status[exchange]["connected"]:
                            # Measure round-trip latency
                            start_time = time.time()
                            
                            # Ping exchange through Redis
                            ping_key = f"exchange:ping:{exchange}"
                            ping_value = str(int(start_time * 1000))
                            
                            await self.redis_client.set(ping_key, ping_value, expire=10)
                            ping_response = await self.redis_client.get(ping_key)
                            
                            if ping_response and ping_response == ping_value:
                                latency = (time.time() - start_time) * 1000  # Convert to ms
                                
                                # Update latency metrics
                                self.latency_metrics[exchange] = {
                                    "last_measurement": latency,
                                    "timestamp": time.time()
                                }
                                
                                # Update exchange status with latency
                                self.exchange_status[exchange]["latency_ms"] = latency
                                
                except Exception as e:
                    self.logger.error(f"Error measuring exchange latency: {e}")
                
                # Wait before next measurement
                await asyncio.sleep(self.config["latency_measurement_interval"])
                
        except asyncio.CancelledError:
            self.logger.info("Latency measurement task cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error in latency measurement: {e}")
    
    async def _task_exchange_heartbeat(self):
        """Background task to monitor exchange connectivity."""
        try:
            while not self.shutdown_event.is_set():
                try:
                    current_time = time.time()
                    
                    for exchange, status in self.exchange_status.items():
                        # Check if exchange heartbeat is recent
                        time_since_heartbeat = current_time - status["last_heartbeat"]
                        
                        if status["connected"] and time_since_heartbeat > self.config["heartbeat_interval"] * 3:
                            # Exchange connection may be stale
                            self.logger.warning(f"Exchange {exchange} heartbeat timed out after {time_since_heartbeat:.1f}s")
                            
                            # Update status
                            self.exchange_status[exchange]["connected"] = False
                            self.exchange_status[exchange]["active"] = False
                            
                            # Publish status update
                            if self.event_bus:
                                await self.event_bus.publish("exchange_status", {
                                    "exchange": exchange,
                                    "status": "disconnected",
                                    "reason": "heartbeat_timeout"
                                })
                                
                except Exception as e:
                    self.logger.error(f"Error in exchange heartbeat monitoring: {e}")
                
                # Wait before next check
                await asyncio.sleep(self.config["heartbeat_interval"])
                
        except asyncio.CancelledError:
            self.logger.info("Exchange heartbeat task cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error in exchange heartbeat task: {e}")
    
    async def _task_cleanup_stale_arbitrages(self):
        """Background task to clean up stale arbitrage opportunities."""
        try:
            while not self.shutdown_event.is_set():
                try:
                    current_time = time.time()
                    
                    # Check for timed out arbitrage executions
                    for arb_id, arb_data in list(self.active_arbitrages.items()):
                        time_active = current_time - arb_data["created_at"]
                        
                        if time_active > self.config["execution_timeout"]:
                            # Arbitrage execution has timed out
                            await self._cancel_arbitrage(arb_id, reason="Execution timeout")
                            
                except Exception as e:
                    self.logger.error(f"Error in arbitrage cleanup: {e}")
                
                # Wait before next cleanup
                await asyncio.sleep(5)  # Check every 5 seconds
                
        except asyncio.CancelledError:
            self.logger.info("Arbitrage cleanup task cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error in arbitrage cleanup task: {e}")
    
    # Helper methods
    
    async def _scan_all_opportunities(self):
        """Scan for arbitrage opportunities across all monitored symbols and exchanges."""
        # Skip if not enough exchanges are active
        active_exchanges = [ex for ex, status in self.exchange_status.items() if status["active"]]
        if len(active_exchanges) < 2:
            return
            
        # Scan each monitored symbol
        for symbol in self.config["monitored_symbols"]:
            await self._scan_symbol_opportunities(symbol, active_exchanges)
    
    async def _scan_symbol_opportunities(self, symbol: str, active_exchanges: List[str]):
        """Scan for arbitrage opportunities for a specific symbol across active exchanges."""
        # Build price comparison matrix
        price_data = {}
        
        for exchange in active_exchanges:
            if exchange in self.market_data and symbol in self.market_data[exchange]:
                market_data = self.market_data[exchange][symbol]
                
                # Check if data is fresh (within 10 seconds)
                if time.time() - market_data["updated_at"] < 10:
                    price_data[exchange] = {
                        "bid": market_data["bid"],
                        "ask": market_data["ask"],
                        "timestamp": market_data["timestamp"]
                    }
        
        # Need at least 2 exchanges with price data
        if len(price_data) < 2:
            return
            
        # Find opportunities between exchange pairs
        exchanges = list(price_data.keys())
        
        for i in range(len(exchanges)):
            for j in range(i+1, len(exchanges)):
                ex1 = exchanges[i]
                ex2 = exchanges[j]
                
                # Check bid/ask spread between exchanges
                # Ex1 buy (ask) vs Ex2 sell (bid)
                ex1_buy_price = price_data[ex1]["ask"]
                ex2_sell_price = price_data[ex2]["bid"]
                
                spread_1to2 = (ex2_sell_price / ex1_buy_price - 1) * 100
                
                # Ex2 buy (ask) vs Ex1 sell (bid)
                ex2_buy_price = price_data[ex2]["ask"]
                ex1_sell_price = price_data[ex1]["bid"]
                
                spread_2to1 = (ex1_sell_price / ex2_buy_price - 1) * 100
                
                # Check if either spread exceeds minimum threshold
                min_threshold = self.config["min_price_difference_percent"]
                
                if spread_1to2 > min_threshold:
                    # Opportunity: Buy on Ex1, Sell on Ex2
                    await self._evaluate_opportunity(
                        buy_exchange=ex1,
                        sell_exchange=ex2,
                        symbol=symbol,
                        buy_price=ex1_buy_price,
                        sell_price=ex2_sell_price,
                        spread_percent=spread_1to2
                    )
                
                if spread_2to1 > min_threshold:
                    # Opportunity: Buy on Ex2, Sell on Ex1
                    await self._evaluate_opportunity(
                        buy_exchange=ex2,
                        sell_exchange=ex1,
                        symbol=symbol,
                        buy_price=ex2_buy_price,
                        sell_price=ex1_sell_price,
                        spread_percent=spread_2to1
                    )
    
    async def _evaluate_opportunity(self, buy_exchange: str, sell_exchange: str,
                                   symbol: str, buy_price: float, sell_price: float,
                                   spread_percent: float):
        """Evaluate and possibly execute an arbitrage opportunity."""
        # Calculate fees
        buy_fee_rate = self.fee_structures.get(buy_exchange, {}).get("taker", 0.002)
        sell_fee_rate = self.fee_structures.get(sell_exchange, {}).get("taker", 0.002)
        
        # Adjust spread for fees
        net_spread_percent = spread_percent - (buy_fee_rate * 100) - (sell_fee_rate * 100)
        
        # Check if opportunity is still profitable after fees
        if net_spread_percent <= 0:
            return
            
        # Calculate optimal position size based on risk parameters
        base_position_size = self.config["max_position_size_usd"]
        
        # Scale position size based on spread (more profitable = larger size)
        position_scaling = min(1.0, net_spread_percent / 5.0)  # Scale up to 100% at 5% spread
        position_scaling = max(0.1, position_scaling)  # At least 10% of max size
        
        # Apply risk control scaling
        risk_scaling = self.config["risk_control"]["position_size_scaling"]
        
        # Calculate final position size
        position_size_usd = base_position_size * position_scaling * risk_scaling
        
        # Calculate quantity based on buy price
        quantity = position_size_usd / buy_price
        
        # Calculate expected profit
        expected_profit = (position_size_usd * net_spread_percent / 100)
        
        # Create arbitrage ID
        arbitrage_id = f"{buy_exchange}_{sell_exchange}_{symbol}_{int(time.time())}"
        
        # Record opportunity detection
        self.execution_stats["opportunities_detected"] += 1
        
        # Create arbitrage data
        arbitrage_data = {
            "id": arbitrage_id,
            "buy_exchange": buy_exchange,
            "sell_exchange": sell_exchange,
            "symbol": symbol,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "quantity": quantity,
            "position_size_usd": position_size_usd,
            "gross_spread_percent": spread_percent,
            "net_spread_percent": net_spread_percent,
            "expected_profit_usd": expected_profit,
            "created_at": time.time(),
            "status": "pending"
        }
        
        # Store in active arbitrages
        self.active_arbitrages[arbitrage_id] = arbitrage_data
        
        # Log the opportunity
        self.logger.info(
            f"Arbitrage opportunity: {symbol} buy@{buy_exchange}:{buy_price:.2f} "
            f"sell@{sell_exchange}:{sell_price:.2f} spread:{net_spread_percent:.2f}% "
            f"profit:{expected_profit:.2f}USD"
        )
        
        # Execute the arbitrage if event bus is available
        if self.event_bus:
            await self.event_bus.publish("execute_arbitrage", arbitrage_data)
            
        # Store opportunity in Redis
        await self.redis_client.set(
            f"arbitrage:opportunity:{arbitrage_id}",
            json.dumps(arbitrage_data)
        )
    
    async def _check_arbitrage_opportunity(self, updated_exchange: str, symbol: str):
        """Check if a market data update creates arbitrage opportunities."""
        # Skip if this symbol isn't in our monitored list
        if symbol not in self.config["monitored_symbols"]:
            return
            
        # Get active exchanges excluding the updated one
        active_exchanges = [
            ex for ex, status in self.exchange_status.items() 
            if status["active"] and ex != updated_exchange
        ]
        
        if not active_exchanges:
            return
            
        # Get updated price data
        if updated_exchange not in self.market_data or symbol not in self.market_data[updated_exchange]:
            return
            
        updated_data = self.market_data[updated_exchange][symbol]
        updated_bid = updated_data["bid"]
        updated_ask = updated_data["ask"]
        
        # Compare with other exchanges
        for other_exchange in active_exchanges:
            if other_exchange not in self.market_data or symbol not in self.market_data[other_exchange]:
                continue
                
            other_data = self.market_data[other_exchange][symbol]
            other_bid = other_data["bid"]
            other_ask = other_data["ask"]
            
            # Check both directions
            # Updated exchange buy (ask) vs other exchange sell (bid)
            spread_updated_to_other = (other_bid / updated_ask - 1) * 100
            
            # Other exchange buy (ask) vs updated exchange sell (bid)
            spread_other_to_updated = (updated_bid / other_ask - 1) * 100
            
            # Check if either spread exceeds minimum threshold
            min_threshold = self.config["min_price_difference_percent"]
            
            if spread_updated_to_other > min_threshold:
                # Opportunity: Buy on updated exchange, Sell on other exchange
                await self._evaluate_opportunity(
                    buy_exchange=updated_exchange,
                    sell_exchange=other_exchange,
                    symbol=symbol,
                    buy_price=updated_ask,
                    sell_price=other_bid,
                    spread_percent=spread_updated_to_other
                )
            
            if spread_other_to_updated > min_threshold:
                # Opportunity: Buy on other exchange, Sell on updated exchange
                await self._evaluate_opportunity(
                    buy_exchange=other_exchange,
                    sell_exchange=updated_exchange,
                    symbol=symbol,
                    buy_price=other_ask,
                    sell_price=updated_bid,
                    spread_percent=spread_other_to_updated
                )
    
    async def _cancel_arbitrage(self, arbitrage_id: str, reason: str):
        """Cancel an active arbitrage execution."""
        if arbitrage_id not in self.active_arbitrages:
            return
            
        arbitrage_data = self.active_arbitrages[arbitrage_id]
        self.logger.warning(f"Cancelling arbitrage {arbitrage_id}: {reason}")
        
        # Remove from active arbitrages
        del self.active_arbitrages[arbitrage_id]
        
        # Publish cancellation event
        if self.event_bus:
            await self.event_bus.publish("arbitrage_cancelled", {
                "arbitrage_id": arbitrage_id,
                "reason": reason,
                "data": arbitrage_data
            })
            
        # Update Redis
        await self.redis_client.set(
            f"arbitrage:cancelled:{arbitrage_id}",
            json.dumps({
                "timestamp": time.time(),
                "reason": reason,
                "data": arbitrage_data
            })
        )
        
        # Update execution stats
        self.execution_stats["failed_executions"] += 1

# Main entry point for standalone execution
if __name__ == "__main__":
    import logging
    import sys
    from utils.redis_client import RedisClient
    from utils.event_bus import EventBus
    from utils.async_support import AsyncSupport
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )
    
    logger = logging.getLogger("CrossPlatformArbitrage")
    
    async def main():
        # Create event bus
        event_bus = EventBus()
        
        # Create Redis client with required configuration
        redis_client = RedisClient(
            host="localhost",
            port=6380,
            password="QuantumNexus2025",
            db=0
        )
        
        # Connect to Redis
        try:
            await redis_client.connect()
            logger.info("Connected to Redis Quantum Nexus")
        except Exception as e:
            logger.warning(f"⚠️ Failed to connect to Redis: {e} - running in limited mode")
            
        # Create async support
        async_support = AsyncSupport()
        
        # Create arbitrage module
        module = CrossPlatformArbitrage(
            redis_client=redis_client,
            event_bus=event_bus,
            async_support=async_support,
            config_path="config/arbitrage_config.json"
        )
        
        # Initialize module
        if not await module.initialize():
            logger.warning("⚠️ Failed to initialize Cross-Platform Arbitrage Module - running in limited mode")
            
        logger.info("Cross-Platform Arbitrage Module running...")
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            # Clean shutdown
            await module.on_shutdown({})
            await redis_client.close()
    
    # Run the async main function
    asyncio.run(main())
