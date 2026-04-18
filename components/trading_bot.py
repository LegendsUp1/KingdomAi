"""
Trading Bot Component for Kingdom AI.

This module provides trading functionality for the Kingdom AI system.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class TradingBot:
    """
    Trading Bot for the Kingdom AI system.
    
    Handles trading strategies, market analysis, and order execution.
    """
    
    def __init__(self, event_bus=None, config=None):
        """
        Initialize the Trading Bot component.
        
        Args:
            event_bus: Event bus for component communication
            config: Configuration manager
        """
        self.event_bus = event_bus
        self.config = config
        self.status = "initializing"
        self.strategies = {}
        self.active_orders = {}
        self.connected_exchanges = []
        
    async def initialize(self):
        """Initialize the Trading Bot component."""
        logger.info("Initializing Trading Bot...")
        
        try:
            # Register with event bus
            if self.event_bus:
                self.event_bus.subscribe("trading.order", self._handle_order)
                self.event_bus.subscribe("trading.strategy", self._handle_strategy)
                self.event_bus.subscribe("market.data", self._handle_market_data)
                
                # Publish ready status
                self.event_bus.publish("component.ready", {
                    "component": "TradingBot",
                    "status": "ready"
                })
            
            # Set component as ready
            self.status = "ready"
            logger.info("Trading Bot initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Trading Bot: {e}")
            self.status = "failed"
            
            # Publish failed status
            if self.event_bus:
                self.event_bus.publish("component.failed", {
                    "component": "TradingBot",
                    "error": str(e)
                })
            return False
    
    def get_status(self):
        """Get the current status of the Trading Bot."""
        return self.status
    
    async def _handle_order(self, data):
        """Handle trading order events."""
        try:
            order_type = data.get('type')
            symbol = data.get('symbol')
            amount = data.get('amount')
            
            logger.info(f"Processing {order_type} order for {symbol}, amount: {amount}")
            
            # Simulate order processing
            await asyncio.sleep(0.5)
            
            # Add to active orders
            order_id = f"order_{len(self.active_orders) + 1}"
            self.active_orders[order_id] = {
                'type': order_type,
                'symbol': symbol,
                'amount': amount,
                'status': 'executed'
            }
            
            # Publish order executed event
            if self.event_bus:
                self.event_bus.publish("trading.order.executed", {
                    'order_id': order_id,
                    'status': 'executed'
                })
                
        except Exception as e:
            logger.error(f"Error handling order: {e}")
    
    async def _handle_strategy(self, data):
        """Handle trading strategy events."""
        try:
            strategy_name = data.get('name')
            strategy_config = data.get('config', {})
            
            logger.info(f"Configuring trading strategy: {strategy_name}")
            
            # Add strategy to active strategies
            self.strategies[strategy_name] = strategy_config
            
            # Publish strategy activated event
            if self.event_bus:
                self.event_bus.publish("trading.strategy.activated", {
                    'strategy': strategy_name,
                    'status': 'active'
                })
                
        except Exception as e:
            logger.error(f"Error handling strategy: {e}")
    
    async def _handle_market_data(self, data):
        """Handle market data events."""
        try:
            symbol = data.get('symbol')
            price = data.get('price')
            
            logger.debug(f"Received market data for {symbol}: {price}")
            
            # Process with active strategies
            for strategy_name, strategy_config in self.strategies.items():
                if strategy_config.get('symbol') == symbol:
                    # Execute strategy logic
                    await self._execute_strategy(strategy_name, symbol, price)
                    
        except Exception as e:
            logger.error(f"Error handling market data: {e}")
    
    async def _execute_strategy(self, strategy_name, symbol, price):
        """Execute a trading strategy based on market data."""
        try:
            strategy = self.strategies.get(strategy_name)
            if not strategy:
                return

            history_key = f"_price_history_{symbol}"
            if not hasattr(self, history_key):
                setattr(self, history_key, [])
            price_history: list = getattr(self, history_key)
            price_history.append(float(price))

            max_lookback = max(strategy.get('long_period', 50), 60)
            if len(price_history) > max_lookback:
                price_history[:] = price_history[-max_lookback:]

            signal = None

            if strategy.get('type') == 'follow_trend':
                period = strategy.get('period', 20)
                if len(price_history) >= period:
                    ma = sum(price_history[-period:]) / period
                    if price > ma * 1.005:
                        signal = {'action': 'buy', 'reason': f'Price {price:.2f} above MA({period}) {ma:.2f}'}
                    elif price < ma * 0.995:
                        signal = {'action': 'sell', 'reason': f'Price {price:.2f} below MA({period}) {ma:.2f}'}

            elif strategy.get('type') == 'mean_reversion':
                period = strategy.get('period', 20)
                std_threshold = strategy.get('std_threshold', 2.0)
                if len(price_history) >= period:
                    window = price_history[-period:]
                    mean_price = sum(window) / len(window)
                    variance = sum((p - mean_price) ** 2 for p in window) / len(window)
                    std_dev = variance ** 0.5
                    if std_dev > 0:
                        z_score = (price - mean_price) / std_dev
                        if z_score > std_threshold:
                            signal = {
                                'action': 'sell',
                                'reason': f'Mean reversion: z={z_score:.2f} > {std_threshold} (price overextended up)',
                            }
                        elif z_score < -std_threshold:
                            signal = {
                                'action': 'buy',
                                'reason': f'Mean reversion: z={z_score:.2f} < -{std_threshold} (price overextended down)',
                            }

            if signal:
                signal.update({
                    'strategy': strategy_name,
                    'symbol': symbol,
                    'price': price,
                })
                logger.info(f"Strategy signal: {signal}")
                if self.event_bus:
                    self.event_bus.publish("trading.signal", signal)
            else:
                logger.debug(f"No signal from {strategy_name} for {symbol} at {price}")

        except Exception as e:
            logger.error(f"Error executing strategy {strategy_name}: {e}")
    
    async def execute_trade(self, symbol, amount, order_type="market"):
        """
        Execute a trade with the specified parameters.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")
            amount: Amount to trade
            order_type: Type of order (market, limit, etc.)
            
        Returns:
            Dict containing order information
        """
        try:
            logger.info(f"Executing {order_type} trade: {amount} {symbol}")
            
            # Simulate trade execution
            await asyncio.sleep(0.5)
            
            # Create order record
            order_id = f"order_{len(self.active_orders) + 1}"
            order = {
                'id': order_id,
                'symbol': symbol,
                'amount': amount,
                'type': order_type,
                'status': 'executed',
                'timestamp': asyncio.get_event_loop().time()
            }
            
            # Store order
            self.active_orders[order_id] = order
            
            # Publish order event if event bus available
            if self.event_bus:
                self.event_bus.publish("trading.order.executed", order)
                
            return order
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            
            # Publish error event if event bus available
            if self.event_bus:
                self.event_bus.publish("trading.order.failed", {
                    'symbol': symbol,
                    'amount': amount,
                    'type': order_type,
                    'error': str(e)
                })
                
            return {'status': 'failed', 'error': str(e)}
    
    def get_active_orders(self):
        """Get all active orders."""
        return self.active_orders
    
    def get_strategies(self):
        """Get all active trading strategies."""
        return self.strategies
        
    async def shutdown(self):
        """Shutdown the Trading Bot component."""
        logger.info("Shutting down Trading Bot...")
        
        try:
            # Unsubscribe from event bus
            if self.event_bus:
                self.event_bus.unsubscribe("trading.order", self._handle_order)
                self.event_bus.unsubscribe("trading.strategy", self._handle_strategy)
                self.event_bus.unsubscribe("market.data", self._handle_market_data)
                
                # Publish shutdown event
                self.event_bus.publish("component.shutdown", {
                    "component": "TradingBot"
                })
                
            # Cancel any pending trades or operations
            self.active_orders = {}
            self.strategies = {}
            
            self.status = "shutdown"
            logger.info("Trading Bot shutdown complete")
            return True
            
        except Exception as e:
            logger.error(f"Error during Trading Bot shutdown: {e}")
            return False
