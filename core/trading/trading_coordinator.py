"""
Kingdom AI Trading Coordinator - SOTA 2026 Edition
Unified coordination layer ensuring all trading components work together seamlessly
with instant data transfer, Ollama brain integration, and maximum speed optimization

SOTA 2026 Features:
- Lock-free ring buffers (Disruptor pattern)
- Priority-based event processing
- Sub-millisecond tick-to-signal pipeline
- Real-time feature stores for ML inference
- uvloop for faster asyncio event loop
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import time
from collections import deque
import numpy as np

# SOTA 2026: Import high-speed pipeline components
try:
    from core.high_speed_pipeline import (
        get_high_speed_event_bus,
        get_market_data_pipeline,
        get_signal_generator,
        HighSpeedEventBus,
        MarketDataPipeline,
        HighSpeedSignalGenerator,
        EventPriority,
    )
    HAS_HIGH_SPEED_PIPELINE = True
except ImportError:
    HAS_HIGH_SPEED_PIPELINE = False

logger = logging.getLogger(__name__)


class TradingCoordinator:
    """
    Central coordinator that unifies all trading components into a single high-performance system
    Ensures instant data flow, Ollama brain consultation, and maximum profit optimization
    """
    
    def __init__(self, event_bus=None, ollama_brain=None, trading_system=None):
        self.event_bus = event_bus
        self.ollama_brain = ollama_brain
        self.trading_system = trading_system
        
        # Component registry
        self.components = {
            'quantum_ai_engine': None,
            'ontology': None,
            'market_data_provider': None,
            'signal_generator': None,
            'order_executor': None,
            'risk_manager': None
        }
        
        # Data flow optimization
        self.data_pipeline = deque(maxlen=10000)  # High-speed data queue
        self.signal_cache = {}
        self.market_data_cache = {}
        
        # Performance metrics
        self.metrics = {
            'signals_generated': 0,
            'trades_executed': 0,
            'total_latency_ms': 0.0,
            'avg_latency_ms': 0.0,
            'data_transfers': 0,
            'ollama_consultations': 0,
            'successful_trades': 0,
            'failed_trades': 0
        }
        
        # Coordination settings
        self.batch_size = 100  # Process 100 symbols simultaneously
        self.update_interval = 0.001  # 1ms coordination cycle
        self.max_concurrent_operations = 1000
        
        # Active coordination
        self.is_coordinating = False
        self.coordination_tasks = []
        
        # SOTA 2026: High-speed pipeline components
        self.high_speed_event_bus: Optional[HighSpeedEventBus] = None
        self.market_data_pipeline: Optional[MarketDataPipeline] = None
        self.high_speed_signal_generator: Optional[HighSpeedSignalGenerator] = None
        self._high_speed_initialized = False
        
        # Initialize high-speed pipeline if available
        if HAS_HIGH_SPEED_PIPELINE:
            self._init_high_speed_pipeline()
        
        logger.info("🎯 Trading Coordinator initialized - Unified system ready")
        logger.info(f"   SOTA 2026 High-Speed Pipeline: {'✅ Enabled' if HAS_HIGH_SPEED_PIPELINE else '❌ Disabled'}")
    
    def _init_high_speed_pipeline(self):
        """Initialize SOTA 2026 high-speed trading pipeline."""
        try:
            self.high_speed_event_bus = get_high_speed_event_bus()
            self.market_data_pipeline = get_market_data_pipeline()
            self.high_speed_signal_generator = get_signal_generator()
            self._high_speed_initialized = True
            
            # Subscribe to high-speed events
            self.high_speed_event_bus.subscribe(
                'trading.signal',
                self._on_high_speed_signal,
                use_ring_buffer=True
            )
            self.high_speed_event_bus.subscribe(
                'market.tick',
                self._on_high_speed_tick,
                use_ring_buffer=True
            )
            
            logger.info("🚀 SOTA 2026 High-Speed Pipeline initialized")
        except Exception as e:
            logger.error(f"Failed to initialize high-speed pipeline: {e}")
            self._high_speed_initialized = False
    
    def _on_high_speed_signal(self, event_type: str, data: dict):
        """Handle high-speed trading signals."""
        if data.get('urgency', 0) >= 8:
            # Critical signal - immediate action
            self.signal_cache[data['symbol']] = data
            self.metrics['signals_generated'] += 1
    
    async def _on_high_speed_tick(self, event_type: str, data: dict):
        """Handle high-speed market ticks."""
        symbol = data.get('symbol')
        if symbol:
            self.market_data_cache[symbol] = data
            self.metrics['data_transfers'] += 1
    
    def process_tick_fast(self, symbol: str, price: float, volume: float,
                          bid: float = 0.0, ask: float = 0.0) -> Optional[dict]:
        """
        Process market tick through SOTA 2026 high-speed pipeline.
        Target: <100μs processing time.
        """
        if not self._high_speed_initialized or not self.market_data_pipeline:
            return None
        
        # Process through high-speed pipeline
        features = self.market_data_pipeline.process_tick(symbol, price, volume, bid, ask)
        
        # Generate signal
        if self.high_speed_signal_generator:
            signal = self.high_speed_signal_generator.generate_signal(symbol)
            if signal and signal.action != 'hold':
                return {
                    'symbol': signal.symbol,
                    'action': signal.action,
                    'confidence': signal.confidence,
                    'features': features,
                }
        
        return features
    
    def get_high_speed_metrics(self) -> dict:
        """Get SOTA 2026 high-speed pipeline metrics."""
        metrics = {'high_speed_enabled': self._high_speed_initialized}
        
        if self._high_speed_initialized:
            if self.high_speed_event_bus:
                metrics['event_bus'] = self.high_speed_event_bus.get_metrics()
            if self.market_data_pipeline:
                metrics['pipeline'] = self.market_data_pipeline.get_metrics()
            if self.high_speed_signal_generator:
                metrics['signal_generator'] = self.high_speed_signal_generator.get_metrics()
        
        return metrics
    
    def register_component(self, component_name: str, component: Any):
        """Register a trading component for coordination"""
        if component_name in self.components:
            self.components[component_name] = component
            logger.info(f"✅ Registered component: {component_name}")
            
            # Connect component to event bus
            if self.event_bus and hasattr(component, 'event_bus'):
                component.event_bus = self.event_bus
            
            # Connect component to Ollama brain
            if self.ollama_brain and hasattr(component, 'ollama_brain'):
                component.ollama_brain = self.ollama_brain
        else:
            logger.warning(f"Unknown component: {component_name}")
    
    async def start_unified_trading(self, symbols: List[str]):
        """Start unified trading across all components"""
        if self.is_coordinating:
            logger.warning("Trading coordination already active")
            return
        
        self.is_coordinating = True
        logger.info(f"🚀 Starting unified trading for {len(symbols)} symbols")
        
        # Initialize all components
        await self._initialize_components()
        
        # Start coordination tasks
        self.coordination_tasks = [
            asyncio.create_task(self._data_flow_coordinator(symbols)),
            asyncio.create_task(self._signal_coordinator(symbols)),
            asyncio.create_task(self._execution_coordinator()),
            asyncio.create_task(self._ollama_consultation_coordinator()),
            asyncio.create_task(self._performance_monitor())
        ]
        
        logger.info("✅ All coordination tasks started")
    
    async def stop_unified_trading(self):
        """Stop unified trading gracefully"""
        self.is_coordinating = False
        
        # Cancel all coordination tasks
        for task in self.coordination_tasks:
            task.cancel()
        
        await asyncio.gather(*self.coordination_tasks, return_exceptions=True)
        self.coordination_tasks.clear()
        
        logger.info("🛑 Unified trading stopped")
    
    async def _initialize_components(self):
        """Initialize and interconnect all components"""
        try:
            # Get quantum AI engine from trading system
            if self.trading_system and hasattr(self.trading_system, 'quantum_ai_engine'):
                self.components['quantum_ai_engine'] = self.trading_system.quantum_ai_engine
                
                # Get ontology from quantum AI engine
                if hasattr(self.components['quantum_ai_engine'], 'ontology'):
                    self.components['ontology'] = self.components['quantum_ai_engine'].ontology
            
            # Initialize signal generator
            if self.components['quantum_ai_engine']:
                self.components['signal_generator'] = self.components['quantum_ai_engine']
            
            logger.info("✅ All components initialized and interconnected")
            
        except Exception as e:
            logger.error(f"Component initialization error: {e}")
    
    async def _data_flow_coordinator(self, symbols: List[str]):
        """Coordinate high-speed data flow between all components"""
        while self.is_coordinating:
            try:
                start_time = time.time()
                
                # Batch fetch market data for all symbols
                market_data_batch = await self._fetch_market_data_batch(symbols)
                
                # Instant data transfer to all components
                await self._distribute_market_data(market_data_batch)
                
                # Update metrics
                latency = (time.time() - start_time) * 1000  # Convert to ms
                self.metrics['total_latency_ms'] += latency
                self.metrics['data_transfers'] += 1
                self.metrics['avg_latency_ms'] = (
                    self.metrics['total_latency_ms'] / self.metrics['data_transfers']
                )
                
                # Dynamic sleep for precise timing
                processing_time = time.time() - start_time
                sleep_time = max(0, self.update_interval - processing_time)
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Data flow error: {e}")
                await asyncio.sleep(1)
    
    async def _signal_coordinator(self, symbols: List[str]):
        """Coordinate signal generation across all symbols"""
        while self.is_coordinating:
            try:
                # Process symbols in batches for maximum throughput
                for i in range(0, len(symbols), self.batch_size):
                    batch = symbols[i:i + self.batch_size]
                    
                    # Generate signals for batch
                    signals = await self._generate_signals_batch(batch)
                    
                    # Cache signals for instant access
                    for signal in signals:
                        self.signal_cache[signal.get('symbol')] = signal
                    
                    self.metrics['signals_generated'] += len(signals)
                
                await asyncio.sleep(self.update_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Signal coordination error: {e}")
                await asyncio.sleep(1)
    
    async def _execution_coordinator(self):
        """Coordinate trade execution with maximum speed"""
        while self.is_coordinating:
            try:
                # Get high-urgency signals from cache
                urgent_signals = [
                    signal for signal in self.signal_cache.values()
                    if signal.get('urgency', 0) >= 8
                ]
                
                if urgent_signals:
                    # Execute trades in parallel
                    execution_tasks = [
                        self._execute_single_trade(signal)
                        for signal in urgent_signals[:self.max_concurrent_operations]
                    ]
                    
                    results = await asyncio.gather(*execution_tasks, return_exceptions=True)
                    
                    # Update metrics
                    successful = sum(1 for r in results if r is True)
                    failed = sum(1 for r in results if r is False or isinstance(r, Exception))
                    
                    self.metrics['trades_executed'] += len(results)
                    self.metrics['successful_trades'] += successful
                    self.metrics['failed_trades'] += failed
                
                await asyncio.sleep(self.update_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Execution coordination error: {e}")
                await asyncio.sleep(1)
    
    async def _ollama_consultation_coordinator(self):
        """Coordinate Ollama brain consultations for enhanced decisions"""
        while self.is_coordinating:
            try:
                if not self.ollama_brain:
                    await asyncio.sleep(1)
                    continue
                
                # Get signals that need Ollama consultation
                signals_for_consultation = [
                    signal for signal in self.signal_cache.values()
                    if signal.get('confidence', 0) > 0.6 and signal.get('confidence', 0) < 0.8
                ]
                
                # Consult Ollama for borderline signals
                for signal in signals_for_consultation[:10]:  # Limit to 10 per cycle
                    enhanced_signal = await self._consult_ollama_for_signal(signal)
                    
                    if enhanced_signal:
                        self.signal_cache[signal['symbol']] = enhanced_signal
                        self.metrics['ollama_consultations'] += 1
                
                await asyncio.sleep(0.1)  # 100ms for Ollama consultations
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ollama coordination error: {e}")
                await asyncio.sleep(1)
    
    async def _performance_monitor(self):
        """Monitor and log performance metrics"""
        while self.is_coordinating:
            try:
                await asyncio.sleep(10)  # Log every 10 seconds
                
                logger.info(f"📊 Trading Coordinator Metrics:")
                logger.info(f"   Signals Generated: {self.metrics['signals_generated']}")
                logger.info(f"   Trades Executed: {self.metrics['trades_executed']}")
                logger.info(f"   Success Rate: {self._calculate_success_rate():.1%}")
                logger.info(f"   Avg Latency: {self.metrics['avg_latency_ms']:.2f}ms")
                logger.info(f"   Data Transfers: {self.metrics['data_transfers']}")
                logger.info(f"   Ollama Consultations: {self.metrics['ollama_consultations']}")
                
                # Publish metrics to event bus
                if self.event_bus:
                    await self.event_bus.publish('trading.coordinator.metrics', {
                        'metrics': self.metrics.copy(),
                        'timestamp': datetime.now().isoformat()
                    })
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
    
    async def _fetch_market_data_batch(self, symbols: List[str]) -> List[Dict]:
        """Fetch market data for multiple symbols simultaneously"""
        try:
            # Use quantum AI engine's market data fetching if available
            if self.components['quantum_ai_engine']:
                # Simulate batch fetch - replace with real implementation
                market_data = []
                for symbol in symbols:
                    if symbol in self.market_data_cache:
                        market_data.append(self.market_data_cache[symbol])
                return market_data
            
            return []
            
        except Exception as e:
            logger.error(f"Market data batch fetch error: {e}")
            return []
    
    async def _distribute_market_data(self, market_data_batch: List[Dict]):
        """Distribute market data to all components instantly"""
        try:
            # Update cache for instant access
            for data in market_data_batch:
                if 'symbol' in data:
                    self.market_data_cache[data['symbol']] = data
            
            # Publish to event bus for real-time updates
            if self.event_bus and market_data_batch:
                await self.event_bus.publish('trading.market_data_batch', {
                    'data': market_data_batch,
                    'timestamp': datetime.now().isoformat(),
                    'count': len(market_data_batch)
                })
            
        except Exception as e:
            logger.error(f"Market data distribution error: {e}")
    
    async def _generate_signals_batch(self, symbols: List[str]) -> List[Dict]:
        """Generate trading signals for a batch of symbols"""
        signals = []
        
        try:
            if not self.components['signal_generator']:
                return signals
            
            # Generate signals using quantum AI engine
            for symbol in symbols:
                if symbol in self.market_data_cache:
                    market_data = self.market_data_cache[symbol]
                    
                    # Convert to MarketData object
                    from core.trading.quantum_ai_trader import MarketData
                    md = MarketData(
                        symbol=symbol,
                        timestamp=datetime.now(),
                        open=market_data.get('open', 0.0),
                        high=market_data.get('high', 0.0),
                        low=market_data.get('low', 0.0),
                        close=market_data.get('close', 0.0),
                        volume=market_data.get('volume', 0.0),
                        vwap=market_data.get('vwap', 0.0),
                        volatility=market_data.get('volatility', 0.0)
                    )
                    
                    # Generate signal with error handling
                    try:
                        signal_obj = await self.components['signal_generator'].analyze_market(symbol, md)
                    except Exception as sig_err:
                        logger.debug(f"Signal generation failed for {symbol}: {sig_err}")
                        continue
                    
                    # Convert to dict for caching
                    signal = {
                        'symbol': signal_obj.symbol,
                        'action': signal_obj.action,
                        'confidence': signal_obj.confidence,
                        'price_target': signal_obj.price_target,
                        'stop_loss': signal_obj.stop_loss,
                        'quantity': signal_obj.quantity,
                        'urgency': signal_obj.urgency,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    signals.append(signal)
            
        except Exception as e:
            logger.error(f"Signal generation batch error: {e}")
        
        return signals
    
    async def _execute_single_trade(self, signal: Dict) -> bool:
        """Execute a single trade with maximum speed"""
        try:
            if not self.components['quantum_ai_engine']:
                return False
            
            # Convert dict back to TradingSignal
            from core.trading.quantum_ai_trader import TradingSignal
            signal_obj = TradingSignal(
                symbol=signal['symbol'],
                action=signal['action'],
                confidence=signal['confidence'],
                price_target=signal['price_target'],
                stop_loss=signal['stop_loss'],
                quantity=signal['quantity'],
                timestamp=datetime.now(),
                urgency=signal.get('urgency', 5),
                strategy_id='unified_coordinator'
            )
            
            # Execute through quantum AI engine
            success = await self.components['quantum_ai_engine'].execute_signal(signal_obj)
            
            return success
            
        except Exception as e:
            logger.error(f"Trade execution error for {signal.get('symbol')}: {e}")
            return False
    
    async def _consult_ollama_for_signal(self, signal: Dict) -> Optional[Dict]:
        """Consult Ollama brain for enhanced trading decision"""
        try:
            if not self.ollama_brain:
                return None
            
            prompt = f"""Enhanced trading decision needed:
Symbol: {signal['symbol']}
Action: {signal['action']}
Confidence: {signal['confidence']:.2%}
Price Target: ${signal['price_target']:.2f}

Should I execute this trade? Consider:
1. Current market conditions
2. Risk/reward ratio
3. Confidence level
4. Market volatility

Respond with: EXECUTE, HOLD, or REJECT and confidence adjustment (0-20%)."""
            
            # Handle both sync and async Ollama brain
            if asyncio.iscoroutinefunction(self.ollama_brain.query):
                response = await self.ollama_brain.query(prompt)
            else:
                response = self.ollama_brain.query(prompt)
            
            if response:
                # Parse Ollama response
                if 'EXECUTE' in response.upper():
                    signal['confidence'] = min(signal['confidence'] * 1.15, 1.0)
                    signal['urgency'] = min(signal.get('urgency', 5) + 2, 10)
                    signal['ollama_approved'] = True
                elif 'REJECT' in response.upper():
                    signal['confidence'] = signal['confidence'] * 0.5
                    signal['urgency'] = 1
                    signal['ollama_approved'] = False
                else:  # HOLD
                    signal['urgency'] = max(signal.get('urgency', 5) - 1, 1)
                
                return signal
            
        except Exception as e:
            logger.debug(f"Ollama consultation error: {e}")
        
        return None
    
    def _calculate_success_rate(self) -> float:
        """Calculate trade success rate"""
        total = self.metrics['successful_trades'] + self.metrics['failed_trades']
        if total == 0:
            return 0.0
        return self.metrics['successful_trades'] / total
    
    def get_coordination_status(self) -> Dict[str, Any]:
        """Get current coordination status"""
        return {
            'is_coordinating': self.is_coordinating,
            'active_tasks': len(self.coordination_tasks),
            'registered_components': sum(1 for c in self.components.values() if c is not None),
            'cached_signals': len(self.signal_cache),
            'cached_market_data': len(self.market_data_cache),
            'metrics': self.metrics.copy(),
            'success_rate': self._calculate_success_rate(),
            'avg_latency_ms': self.metrics['avg_latency_ms']
        }
    
    async def optimize_data_flow(self):
        """Optimize data flow for maximum speed"""
        try:
            # Clear stale data from caches
            current_time = time.time()
            
            # Remove signals older than 10 seconds
            stale_signals = [
                symbol for symbol, signal in self.signal_cache.items()
                if (current_time - signal.get('timestamp', 0)) > 10
            ]
            
            for symbol in stale_signals:
                del self.signal_cache[symbol]
            
            # Remove market data older than 5 seconds
            stale_data = [
                symbol for symbol, data in self.market_data_cache.items()
                if (current_time - data.get('timestamp', 0)) > 5
            ]
            
            for symbol in stale_data:
                del self.market_data_cache[symbol]
            
            logger.debug(f"Cache optimization: Removed {len(stale_signals)} signals, {len(stale_data)} market data")
            
        except Exception as e:
            logger.error(f"Data flow optimization error: {e}")
