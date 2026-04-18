"""
Kingdom AI Quantum Trading System
Advanced AI-powered trading with quantum models, ontology, and UHF execution
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import asyncio
import logging
from typing import Dict, List, Tuple, Optional, Any
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import json

logger = logging.getLogger(__name__)

# SOTA 2026: Quantum Enhancement Bridge for real IBM/OpenQuantum hardware
try:
    from core.quantum_enhancement_bridge import get_quantum_bridge, QUANTUM_BRIDGE_AVAILABLE
    from core.quantum_mining import (
        is_real_quantum_available,
        QuantumTradingEnhancer,
        get_quantum_trading_enhancer
    )
    HAS_REAL_QUANTUM = True
except ImportError:
    HAS_REAL_QUANTUM = False
    QUANTUM_BRIDGE_AVAILABLE = False

# SOTA 2026 GPU SCHEDULER: Optimal device assignment for trading AI
try:
    from core.gpu_scheduler import get_gpu_scheduler
    _gpu_scheduler = get_gpu_scheduler()
    _assigned_device = _gpu_scheduler.get_device('trading_ai')  # Gets cuda:1 on dual-GPU systems
    device = torch.device(_assigned_device)
    logger.info(f"🚀 GPU Scheduler assigned device: {_assigned_device}")
except (ImportError, Exception) as e:
    # Fallback if GPU scheduler not available
    if torch.cuda.is_available():
        device = torch.device('cuda')
        logger.info("🚀 GPU acceleration enabled (fallback to default device)")
    else:
        device = torch.device('cpu')
        logger.info("💻 Running on CPU")


@dataclass
class TradingSignal:
    """Enhanced trading signal with confidence and urgency"""
    symbol: str
    action: str  # BUY, SELL, HOLD
    confidence: float
    price_target: float
    stop_loss: float
    quantity: float
    timestamp: datetime
    urgency: int = 5  # 1-10 scale
    strategy_id: str = "quantum_ai"
    risk_score: float = 0.0
    expected_profit: float = 0.0


@dataclass
class MarketData:
    """Comprehensive market data structure"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float = 0.0
    volatility: float = 0.0
    funding_rate: Optional[float] = None
    order_book: Dict[str, Any] = field(default_factory=dict)


class PalantirOntology:
    """
    Advanced Ontology System for Unified Market Intelligence
    Models relationships between all assets, markets, and blockchain data
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.asset_graph = {
            'entities': {
                'assets': {},
                'exchanges': {},
                'blockchains': {},
                'trading_pairs': {},
                'liquidity_pools': {}
            },
            'relationships': {
                'correlations': {},
                'arbitrage_paths': {},
                'liquidity_flows': {},
                'risk_exposures': {}
            }
        }
        self.correlation_matrix = {}
        self.risk_factors = {}
        self.market_regimes = {}
        self.arbitrage_opportunities = []
        
        logger.info("🧠 Palantir Ontology initialized")
    
    def add_asset(self, asset_data: Dict[str, Any]):
        """Add asset to ontology with comprehensive metadata"""
        symbol = asset_data['symbol']
        self.asset_graph['entities']['assets'][symbol] = {
            'type': asset_data.get('type', 'unknown'),
            'market_cap': asset_data.get('market_cap', 0),
            'volume_24h': asset_data.get('volume_24h', 0),
            'volatility': asset_data.get('volatility', 0),
            'sector': asset_data.get('sector', 'unknown'),
            'fundamentals': asset_data.get('fundamentals', {}),
            'on_chain_metrics': asset_data.get('on_chain_metrics', {}),
            'created_at': datetime.now(),
            'last_updated': datetime.now()
        }
        logger.debug(f"Added {symbol} to ontology")
    
    def update_correlations(self, price_data: Dict[str, np.ndarray]):
        """Update correlation matrix with real-time price data"""
        try:
            symbols = list(price_data.keys())
            if len(symbols) < 2:
                return
            
            # Calculate returns
            returns_dict = {}
            for symbol, prices in price_data.items():
                if len(prices) > 1:
                    returns = np.diff(prices) / prices[:-1]
                    returns_dict[symbol] = returns
            
            # Calculate correlations
            for i, symbol1 in enumerate(symbols):
                if symbol1 not in returns_dict:
                    continue
                for j, symbol2 in enumerate(symbols):
                    if i != j and symbol2 in returns_dict:
                        try:
                            corr = np.corrcoef(returns_dict[symbol1], returns_dict[symbol2])[0, 1]
                            if not np.isnan(corr):
                                correlation_key = f"{symbol1}_{symbol2}"
                                self.correlation_matrix[correlation_key] = float(corr)
                        except:
                            pass
            
            logger.debug(f"Updated correlations for {len(symbols)} symbols")
        except Exception as e:
            logger.error(f"Correlation update error: {e}")
    
    def find_arbitrage_opportunities(self, prices: Dict[str, Dict[str, float]]) -> List[Dict]:
        """Find cross-exchange arbitrage opportunities"""
        opportunities = []
        
        try:
            for symbol, exchange_prices in prices.items():
                if len(exchange_prices) < 2:
                    continue
                
                exchanges = list(exchange_prices.keys())
                for i, ex1 in enumerate(exchanges):
                    for j, ex2 in enumerate(exchanges):
                        if i < j:
                            price1 = exchange_prices[ex1]
                            price2 = exchange_prices[ex2]
                            
                            if price1 > 0 and price2 > 0:
                                spread_pct = abs(price1 - price2) / min(price1, price2)
                                
                                if spread_pct > 0.002:  # 0.2% threshold
                                    opportunities.append({
                                        'symbol': symbol,
                                        'buy_exchange': ex1 if price1 < price2 else ex2,
                                        'sell_exchange': ex2 if price1 < price2 else ex1,
                                        'buy_price': min(price1, price2),
                                        'sell_price': max(price1, price2),
                                        'spread_pct': spread_pct,
                                        'profit_potential': spread_pct * 10000,  # Basis points
                                        'timestamp': datetime.now()
                                    })
            
            self.arbitrage_opportunities = opportunities
            
        except Exception as e:
            logger.error(f"Arbitrage detection error: {e}")
        
        return opportunities
    
    async def find_arbitrage_quantum(self, prices: Dict[str, Dict[str, float]]) -> List[Dict]:
        """SOTA 2026: Find arbitrage using real quantum hardware.
        
        Uses Grover's algorithm on real IBM/OpenQuantum QPU for faster detection.
        """
        # First get classical opportunities
        opportunities = self.find_arbitrage_opportunities(prices)
        
        # Enhance with quantum if available
        if HAS_REAL_QUANTUM and is_real_quantum_available():
            try:
                enhancer = get_quantum_trading_enhancer()
                
                # Build price pairs for quantum search
                price_pairs = []
                for symbol, exchange_prices in prices.items():
                    exchanges = list(exchange_prices.keys())
                    for i, ex1 in enumerate(exchanges):
                        for j, ex2 in enumerate(exchanges):
                            if i < j:
                                price_pairs.append((
                                    f"{symbol}_{ex1}_{ex2}",
                                    exchange_prices[ex1],
                                    exchange_prices[ex2]
                                ))
                
                if price_pairs:
                    quantum_result = await enhancer.analyze_arbitrage(price_pairs[:6])
                    
                    if quantum_result.get("quantum_enhanced"):
                        logger.info(f"⚛️ Quantum arbitrage scan found {len(quantum_result.get('opportunities', []))} opportunities")
                        
                        # Add quantum-detected opportunities
                        for qopp in quantum_result.get("opportunities", []):
                            opportunities.append({
                                'symbol': qopp.get('pair', '').split('_')[0],
                                'spread_pct': qopp.get('spread', 0),
                                'confidence': qopp.get('confidence', 0),
                                'quantum_detected': True,
                                'timestamp': datetime.now()
                            })
                            
            except Exception as e:
                logger.debug(f"Quantum arbitrage enhancement skipped: {e}")
        
        return opportunities
    
    def get_asset_relationships(self, symbol: str, threshold: float = 0.6) -> Dict:
        """Get related assets and their relationship strengths"""
        relationships = {}
        
        try:
            for other_symbol in self.asset_graph['entities']['assets']:
                if other_symbol != symbol:
                    correlation_key = f"{symbol}_{other_symbol}"
                    reverse_key = f"{other_symbol}_{symbol}"
                    
                    corr = self.correlation_matrix.get(correlation_key, 
                           self.correlation_matrix.get(reverse_key, 0.0))
                    
                    if abs(corr) > threshold:
                        relationships[other_symbol] = {
                            'correlation': float(corr),
                            'relationship': 'positive' if corr > 0 else 'negative',
                            'strength': abs(corr)
                        }
        except Exception as e:
            logger.error(f"Relationship detection error: {e}")
        
        return relationships
    
    def get_stats(self) -> Dict:
        """Get ontology statistics"""
        return {
            'total_assets': len(self.asset_graph['entities']['assets']),
            'total_correlations': len(self.correlation_matrix),
            'arbitrage_opportunities': len(self.arbitrage_opportunities),
            'market_regimes': len(self.market_regimes)
        }


class QuantumInspiredLayer(nn.Module):
    """Quantum-inspired neural layer using entanglement simulation"""
    
    def __init__(self, input_dim: int, output_dim: int):
        super(QuantumInspiredLayer, self).__init__()
        self.input_dim = input_dim
        self.output_dim = output_dim
        
        # Quantum-inspired weight initialization
        self.weights = nn.Parameter(torch.randn(input_dim, output_dim) / np.sqrt(input_dim))
        self.phase_shift = nn.Parameter(torch.randn(output_dim))
        
        # Entanglement simulation
        self.entanglement_matrix = nn.Parameter(
            torch.eye(output_dim) + 0.1 * torch.randn(output_dim, output_dim)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Quantum state preparation (amplitude encoding)
        amplitudes = torch.softmax(x, dim=-1)
        
        # Quantum gate simulation (unitary transformation)
        transformed = torch.matmul(amplitudes, self.weights)
        
        # Phase shift application
        phase_adjusted = transformed * torch.cos(self.phase_shift)
        
        # Entanglement simulation
        entangled = torch.matmul(phase_adjusted, self.entanglement_matrix)
        
        # Measurement simulation
        probabilities = torch.abs(entangled) ** 2
        normalized = probabilities / (torch.sum(probabilities, dim=-1, keepdim=True) + 1e-8)
        
        return normalized


class QuantumNeuralNetwork(nn.Module):
    """
    Hybrid Quantum-Classical Neural Network for Financial Prediction
    """
    
    def __init__(self, input_size: int = 50, hidden_size: int = 256, 
                 output_size: int = 3, n_qubits: int = 8):
        super(QuantumNeuralNetwork, self).__init__()
        self.n_qubits = n_qubits
        
        # Classical feature encoder
        self.feature_encoder = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.1)
        )
        
        # Quantum-inspired layers
        self.quantum_layer = QuantumInspiredLayer(hidden_size, n_qubits)
        
        # Output heads for different prediction tasks
        self.price_predictor = nn.Linear(n_qubits, output_size)
        self.volatility_predictor = nn.Linear(n_qubits, 1)
        self.regime_predictor = nn.Linear(n_qubits, 3)  # Bull, Bear, Neutral
        
        # Attention mechanism
        self.temporal_attention = nn.MultiheadAttention(
            embed_dim=n_qubits,
            num_heads=4,
            batch_first=True,
            dropout=0.1
        )
    
    def forward(self, x: torch.Tensor, temporal_context: Optional[torch.Tensor] = None):
        # Feature encoding
        encoded = self.feature_encoder(x)
        
        # Quantum-inspired transformation
        quantum_features = self.quantum_layer(encoded)
        
        # Temporal attention if context provided
        if temporal_context is not None and temporal_context.size(0) > 0:
            try:
                attended, _ = self.temporal_attention(
                    quantum_features.unsqueeze(1),
                    temporal_context,
                    temporal_context
                )
                quantum_features = attended.squeeze(1)
            except:
                pass
        
        # Multiple prediction heads
        price_pred = self.price_predictor(quantum_features)
        volatility_pred = torch.exp(self.volatility_predictor(quantum_features))
        regime_probs = torch.softmax(self.regime_predictor(quantum_features), dim=-1)
        
        return {
            'price_prediction': price_pred,
            'volatility_prediction': volatility_pred,
            'regime_probabilities': regime_probs,
            'quantum_features': quantum_features
        }


class AdvancedFeatureEngine:
    """Advanced feature engineering for financial data"""
    
    def __init__(self):
        self.feature_config = {
            'price_features': True,
            'volume_features': True,
            'technical_indicators': True,
            'statistical_features': True
        }
    
    def generate_features(self, market_data: MarketData, 
                         historical_data: Optional[pd.DataFrame] = None) -> np.ndarray:
        """Generate comprehensive feature set"""
        features = []
        
        # Basic price features
        features.extend([
            market_data.open,
            market_data.high,
            market_data.low,
            market_data.close,
            market_data.volume,
            market_data.vwap or market_data.close,
            market_data.volatility
        ])
        
        # Price-based ratios
        if market_data.close > 0:
            features.extend([
                (market_data.high - market_data.low) / market_data.close,  # Range
                market_data.volume / max(market_data.close * 1000, 1),  # Volume intensity
                (market_data.close - market_data.open) / market_data.close if market_data.close > 0 else 0  # Body ratio
            ])
        else:
            features.extend([0, 0, 0])
        
        # Historical features if available
        if historical_data is not None and len(historical_data) > 0:
            try:
                prices = np.array(historical_data['close'].values, dtype=float)
                if len(prices) > 1:
                    returns = np.diff(prices) / prices[:-1]
                    features.extend([
                        np.mean(returns) if len(returns) > 0 else 0,
                        np.std(returns) if len(returns) > 0 else 0,
                        prices[-1] / prices[0] - 1 if prices[0] > 0 else 0
                    ])
                else:
                    features.extend([0, 0, 0])
            except:
                features.extend([0, 0, 0])
        else:
            features.extend([0, 0, 0])
        
        # Pad or truncate to fixed size
        target_size = 50
        if len(features) < target_size:
            features.extend([0] * (target_size - len(features)))
        else:
            features = features[:target_size]
        
        return np.array(features, dtype=np.float32)


class QuantumAITradingEngine:
    """
    Main Quantum AI Trading Engine with Ollama Brain Integration
    Handles auto-trading across all coins, stocks, and markets
    """
    
    def __init__(self, initial_capital: float = 100000, event_bus=None, ollama_brain=None):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {}
        self.trade_history = []
        self.event_bus = event_bus
        self.ollama_brain = ollama_brain
        
        # Core components
        self.ontology = PalantirOntology(event_bus=event_bus)
        self.feature_engine = AdvancedFeatureEngine()
        
        # AI Models
        self.quantum_model = QuantumNeuralNetwork(
            input_size=50,
            hidden_size=256,
            output_size=3,
            n_qubits=8
        ).to(device)
        
        self.quantum_model.eval()  # Set to evaluation mode
        
        # Auto-trading configuration
        self.auto_trading_enabled = True
        self.trading_symbols = []
        self.min_confidence = 0.65
        self.max_position_size = 0.05  # 5% per position
        self.stop_loss_pct = 0.02  # 2%
        self.take_profit_pct = 0.04  # 4%
        
        # Risk management
        self.risk_limits = {
            'max_position_size': 0.05,
            'max_daily_loss': 0.02,
            'max_correlation_exposure': 0.3,
            'var_95': 0.01
        }
        
        # Performance tracking
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_profit': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0
        }
        
        logger.info("🚀 Quantum AI Trading Engine initialized")

        # SOTA 2026: Subscribe to VR / voice trading commands
        self._subscribe_to_vr_commands()

    def _subscribe_to_vr_commands(self):
        """Subscribe to VR/voice system commands for trading control."""
        if not self.event_bus:
            return
        try:
            self.event_bus.subscribe("trading.auto.enable", self._handle_auto_enable_cmd)
            self.event_bus.subscribe("trading.auto.disable", self._handle_auto_disable_cmd)
            self.event_bus.subscribe("trading.voice.order", self._handle_voice_order)
            logger.info("✅ QuantumAITrader subscribed to VR/voice commands")
        except Exception as e:
            logger.warning(f"Trading VR command subscription failed: {e}")

    def _handle_auto_enable_cmd(self, data: dict):
        """Handle trading.auto.enable from VR/voice."""
        symbols = data.get("symbols", ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        self.enable_auto_trading(symbols)

    def _handle_auto_disable_cmd(self, data: dict):
        """Handle trading.auto.disable from VR/voice."""
        self.disable_auto_trading()

    def _handle_voice_order(self, data: dict):
        """Handle trading.voice.order — parse spoken buy/sell commands."""
        command = data.get("command", "")
        source = data.get("source", "unknown")
        logger.info(f"📊 Voice trading order from {source}: {command}")
        # Parse basic commands like "buy bitcoin" or "sell ethereum"
        cmd_lower = command.lower()
        action = "buy" if "buy" in cmd_lower else "sell" if "sell" in cmd_lower else None
        if not action:
            return
        # Map spoken names to symbols
        name_to_symbol = {
            "bitcoin": "BTCUSDT", "btc": "BTCUSDT",
            "ethereum": "ETHUSDT", "eth": "ETHUSDT",
            "solana": "SOLUSDT", "sol": "SOLUSDT",
            "cardano": "ADAUSDT", "ada": "ADAUSDT",
            "bnb": "BNBUSDT", "binance": "BNBUSDT",
            "dogecoin": "DOGEUSDT", "doge": "DOGEUSDT",
            "xrp": "XRPUSDT", "ripple": "XRPUSDT",
        }
        symbol = None
        for name, sym in name_to_symbol.items():
            if name in cmd_lower:
                symbol = sym
                break
        if symbol and self.event_bus:
            self.event_bus.publish("trading.signal_executed", {
                "action": action, "symbol": symbol, "source": source,
                "confidence": 0.75, "voice_command": True,
            })
            logger.info(f"📊 Voice trade: {action} {symbol}")

    def enable_auto_trading(self, symbols: List[str]):
        """Enable auto-trading for specified symbols"""
        self.auto_trading_enabled = True
        self.trading_symbols = symbols
        
        # Add symbols to ontology
        for symbol in symbols:
            self.ontology.add_asset({
                'symbol': symbol,
                'type': self._detect_asset_type(symbol),
                'market_cap': 0,
                'volume_24h': 0,
                'volatility': 0.0
            })
        
        logger.info(f"✅ Auto-trading enabled for {len(symbols)} symbols")
        
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish('trading.auto_enabled', {
                'symbol_count': len(symbols),
                'timestamp': datetime.now().isoformat()
            }))
    
    def disable_auto_trading(self):
        """Disable auto-trading"""
        self.auto_trading_enabled = False
        logger.info("🛑 Auto-trading disabled")
        
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish('trading.auto_disabled', {
                'timestamp': datetime.now().isoformat()
            }))
    
    def _detect_asset_type(self, symbol: str) -> str:
        """Detect asset type from symbol"""
        if any(crypto in symbol.upper() for crypto in ['BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'ADA']):
            return 'crypto'
        return 'stock'
    
    async def analyze_market(self, symbol: str, market_data: MarketData,
                           historical_data: Optional[pd.DataFrame] = None) -> TradingSignal:
        """Comprehensive market analysis using quantum AI"""
        try:
            # Generate features
            features = self.feature_engine.generate_features(market_data, historical_data)
            
            # Quantum AI prediction
            with torch.no_grad():
                feature_tensor = torch.FloatTensor(features).unsqueeze(0).to(device)
                predictions = self.quantum_model(feature_tensor)
                
                # Extract predictions
                price_pred = predictions['price_prediction'][0]
                volatility_pred = predictions['volatility_prediction'][0].item()
                regime_probs = predictions['regime_probabilities'][0]
                
                # Determine action and confidence
                bull_prob = regime_probs[0].item()
                bear_prob = regime_probs[1].item()
                neutral_prob = regime_probs[2].item()
                
                if bull_prob > bear_prob and bull_prob > neutral_prob:
                    action = "BUY"
                    confidence = bull_prob
                elif bear_prob > bull_prob and bear_prob > neutral_prob:
                    action = "SELL"
                    confidence = bear_prob
                else:
                    action = "HOLD"
                    confidence = neutral_prob
            
            # Ollama brain consultation if available
            if self.ollama_brain and confidence > 0.6:
                try:
                    ollama_advice = await self._consult_ollama_brain(symbol, market_data, action, confidence)
                    if ollama_advice:
                        action = ollama_advice.get('action', action)
                        confidence = ollama_advice.get('confidence', confidence)
                except Exception as e:
                    logger.warning(f"Ollama consultation failed: {e}")
            
            # Calculate targets
            current_price = market_data.close
            if action == "BUY":
                price_target = current_price * (1 + self.take_profit_pct)
                stop_loss = current_price * (1 - self.stop_loss_pct)
            elif action == "SELL":
                price_target = current_price * (1 - self.take_profit_pct)
                stop_loss = current_price * (1 + self.stop_loss_pct)
            else:
                price_target = current_price
                stop_loss = current_price
            
            # Calculate position size
            risk_amount = self.current_capital * 0.02  # 2% risk per trade
            price_diff = abs(current_price - stop_loss)
            quantity = (risk_amount / price_diff) if price_diff > 0 else 0
            
            # Apply position limits
            max_quantity = (self.current_capital * self.max_position_size) / current_price
            quantity = min(quantity, max_quantity)
            
            signal = TradingSignal(
                symbol=symbol,
                action=action,
                confidence=confidence,
                price_target=price_target,
                stop_loss=stop_loss,
                quantity=quantity,
                timestamp=datetime.now(),
                urgency=int(confidence * 10),
                strategy_id="quantum_ai",
                risk_score=volatility_pred,
                expected_profit=(price_target - current_price) * quantity if action == "BUY" else (current_price - price_target) * quantity
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Market analysis error for {symbol}: {e}")
            return TradingSignal(
                symbol=symbol,
                action="HOLD",
                confidence=0.0,
                price_target=market_data.close,
                stop_loss=market_data.close,
                quantity=0,
                timestamp=datetime.now()
            )
    
    async def _consult_ollama_brain(self, symbol: str, market_data: MarketData,
                                   action: str, confidence: float) -> Optional[Dict]:
        """Consult Ollama brain for trading advice"""
        try:
            if not self.ollama_brain:
                return None
            
            prompt = f"""Analyze trading opportunity:
Symbol: {symbol}
Current Price: ${market_data.close:.2f}
Volatility: {market_data.volatility:.2%}
Suggested Action: {action}
AI Confidence: {confidence:.2%}

Should I execute this trade? Provide: action (BUY/SELL/HOLD) and confidence (0-1)."""
            
            response = await self.ollama_brain.query(prompt)
            
            if response and 'BUY' in response.upper():
                return {'action': 'BUY', 'confidence': confidence * 1.1}
            elif response and 'SELL' in response.upper():
                return {'action': 'SELL', 'confidence': confidence * 1.1}
            elif response and 'HOLD' in response.upper():
                return {'action': 'HOLD', 'confidence': 0.5}
            
        except Exception as e:
            logger.debug(f"Ollama brain consultation error: {e}")
        
        return None
    
    async def execute_signal(self, signal: TradingSignal) -> bool:
        """Execute trading signal"""
        try:
            if signal.action == "HOLD" or signal.confidence < self.min_confidence:
                return False
            
            # Log the trade
            self.trade_history.append({
                'symbol': signal.symbol,
                'action': signal.action,
                'quantity': signal.quantity,
                'price': signal.price_target,
                'confidence': signal.confidence,
                'timestamp': datetime.now()
            })
            
            self.performance_metrics['total_trades'] += 1
            
            logger.info(f"✅ Executed {signal.action} {signal.symbol} | "
                       f"Qty: {signal.quantity:.4f} | Conf: {signal.confidence:.2%}")
            
            # Publish event
            if self.event_bus:
                await self.event_bus.publish('trading.signal_executed', {
                    'symbol': signal.symbol,
                    'action': signal.action,
                    'confidence': signal.confidence,
                    'timestamp': datetime.now().isoformat()
                })
            
            return True
            
        except Exception as e:
            logger.error(f"Signal execution error: {e}")
            return False
    
    def get_performance_stats(self) -> Dict:
        """Get current performance statistics"""
        win_rate = (self.performance_metrics['winning_trades'] / 
                   max(self.performance_metrics['total_trades'], 1))
        
        return {
            'current_capital': self.current_capital,
            'initial_capital': self.initial_capital,
            'total_profit': self.performance_metrics['total_profit'],
            'total_trades': self.performance_metrics['total_trades'],
            'winning_trades': self.performance_metrics['winning_trades'],
            'win_rate': win_rate,
            'active_positions': len(self.positions),
            'auto_trading_enabled': self.auto_trading_enabled,
            'symbols_tracked': len(self.trading_symbols)
        }
    
    def get_ontology_stats(self) -> Dict:
        """Get ontology statistics"""
        return self.ontology.get_stats()
