#!/usr/bin/env python3
"""
Market Analyzer for Kingdom AI Trading System
Provides market analysis, technical indicators, and trading signals
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

@dataclass
class MarketData:
    """Market data structure"""
    symbol: str
    price: float
    volume: float
    high_24h: float
    low_24h: float
    change_24h: float
    timestamp: datetime

@dataclass
class TechnicalIndicator:
    """Technical indicator result"""
    name: str
    value: float
    signal: str  # buy, sell, hold
    confidence: float

@dataclass
class MarketSignal:
    """Market trading signal"""
    symbol: str
    signal_type: str  # buy, sell, hold
    strength: float  # 0-1
    indicators: List[str]
    timestamp: datetime
    price: float

class MarketAnalyzer:
    """Advanced market analyzer with technical indicators"""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._running = False
        self._market_data: Dict[str, MarketData] = {}
        self._indicators: Dict[str, List[TechnicalIndicator]] = {}
        self._signals: List[MarketSignal] = []
        
    async def initialize(self):
        """Initialize the market analyzer"""
        logger.info("🔄 MarketAnalyzer initializing...")
        self._running = True
        
        if self.event_bus:
            self.event_bus.subscribe('market.data.update', self._handle_market_data)
            self.event_bus.subscribe('market.analysis.request', self._handle_analysis_request)
            
        logger.info("✅ MarketAnalyzer initialized")
        return True
        
    async def start(self):
        """Start market analysis"""
        if not self._running:
            await self.initialize()
            
        logger.info("📊 MarketAnalyzer started")
        return True
        
    async def stop(self):
        """Stop market analysis"""
        self._running = False
        logger.info("⏹️ MarketAnalyzer stopped")
        
    def _handle_market_data(self, data):
        """Handle market data updates"""
        symbol = data.get('symbol')
        if symbol:
            self._market_data[symbol] = MarketData(
                symbol=symbol,
                price=data.get('price', 0.0),
                volume=data.get('volume', 0.0),
                high_24h=data.get('high_24h', 0.0),
                low_24h=data.get('low_24h', 0.0),
                change_24h=data.get('change_24h', 0.0),
                timestamp=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat()))
            )
            
            # Update indicators for this symbol
            self._update_indicators(symbol)
            
    def _handle_analysis_request(self, data):
        """Handle analysis requests"""
        symbol = data.get('symbol')
        analysis_type = data.get('type', 'technical')
        
        if symbol:
            if analysis_type == 'technical':
                return self.get_technical_analysis(symbol)
            elif analysis_type == 'signals':
                return self.get_trading_signals(symbol)
            else:
                return self.get_full_analysis(symbol)
                
        return None
        
    def _update_indicators(self, symbol: str):
        """Update technical indicators for a symbol"""
        if symbol not in self._market_data:
            return
            
        market_data = self._market_data[symbol]
        indicators = []
        
        # RSI (simplified)
        rsi = self._calculate_rsi(market_data)
        indicators.append(TechnicalIndicator("RSI", rsi, self._rsi_signal(rsi), 0.8))
        
        # Moving Average (simplified)
        ma = self._calculate_moving_average(market_data)
        indicators.append(TechnicalIndicator("MA", ma, self._ma_signal(market_data.price, ma), 0.7))
        
        # Volume Analysis
        volume_signal = self._analyze_volume(market_data)
        indicators.append(TechnicalIndicator("Volume", market_data.volume, volume_signal, 0.6))
        
        # Price Momentum
        momentum = self._calculate_momentum(market_data)
        indicators.append(TechnicalIndicator("Momentum", momentum, self._momentum_signal(momentum), 0.7))
        
        self._indicators[symbol] = indicators
        
    def _calculate_rsi(self, market_data: MarketData, period: int = 14) -> float:
        """Calculate RSI indicator"""
        # Simplified RSI calculation
        if market_data.change_24h > 0:
            return min(95, 50 + abs(market_data.change_24h) * 100)
        else:
            return max(5, 50 - abs(market_data.change_24h) * 100)
            
    def _rsi_signal(self, rsi: float) -> str:
        """Generate signal from RSI"""
        if rsi < 30:
            return "buy"
        elif rsi > 70:
            return "sell"
        else:
            return "hold"
            
    def _calculate_moving_average(self, market_data: MarketData) -> float:
        """Calculate moving average"""
        # Simplified MA - use current price with small adjustment
        return market_data.price * (1 + market_data.change_24h * 0.5)
        
    def _ma_signal(self, price: float, ma: float) -> str:
        """Generate signal from moving average"""
        if price > ma * 1.02:
            return "buy"
        elif price < ma * 0.98:
            return "sell"
        else:
            return "hold"
            
    def _analyze_volume(self, market_data: MarketData) -> str:
        """Analyze volume for signals"""
        # Simplified volume analysis
        if market_data.volume > 1000000 and market_data.change_24h > 0:
            return "buy"
        elif market_data.volume > 1000000 and market_data.change_24h < 0:
            return "sell"
        else:
            return "hold"
            
    def _calculate_momentum(self, market_data: MarketData) -> float:
        """Calculate price momentum"""
        return market_data.change_24h * 100  # Convert to percentage
        
    def _momentum_signal(self, momentum: float) -> str:
        """Generate signal from momentum"""
        if momentum > 5:
            return "buy"
        elif momentum < -5:
            return "sell"
        else:
            return "hold"
            
    def get_technical_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get technical analysis for a symbol"""
        if symbol not in self._indicators:
            self._update_indicators(symbol)
            
        indicators = self._indicators.get(symbol, [])
        
        return {
            'symbol': symbol,
            'indicators': [
                {
                    'name': ind.name,
                    'value': ind.value,
                    'signal': ind.signal,
                    'confidence': ind.confidence
                } for ind in indicators
            ],
            'timestamp': datetime.now().isoformat()
        }
        
    def get_trading_signals(self, symbol: str) -> Dict[str, Any]:
        """Get trading signals for a symbol"""
        if symbol not in self._indicators:
            self._update_indicators(symbol)
            
        indicators = self._indicators.get(symbol, [])
        if not indicators:
            return {'symbol': symbol, 'signal': 'hold', 'strength': 0.0}
            
        # Calculate overall signal
        buy_signals = [ind for ind in indicators if ind.signal == 'buy']
        sell_signals = [ind for ind in indicators if ind.signal == 'sell']
        
        signal_strength = 0.0
        signal_type = 'hold'
        
        if len(buy_signals) > len(sell_signals):
            signal_type = 'buy'
            signal_strength = sum(ind.confidence for ind in buy_signals) / len(buy_signals)
        elif len(sell_signals) > len(buy_signals):
            signal_type = 'sell'
            signal_strength = sum(ind.confidence for ind in sell_signals) / len(sell_signals)
        else:
            signal_strength = 0.5
            
        return {
            'symbol': symbol,
            'signal': signal_type,
            'strength': signal_strength,
            'indicators': [ind.name for ind in indicators],
            'timestamp': datetime.now().isoformat()
        }
        
    def get_full_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get complete market analysis"""
        technical = self.get_technical_analysis(symbol)
        signals = self.get_trading_signals(symbol)
        
        return {
            'symbol': symbol,
            'technical_analysis': technical,
            'trading_signals': signals,
            'market_data': self._market_data.get(symbol).__dict__ if symbol in self._market_data else None,
            'timestamp': datetime.now().isoformat()
        }
        
    def get_all_signals(self) -> List[Dict[str, Any]]:
        """Get all current trading signals"""
        signals = []
        for symbol in self._market_data.keys():
            signal_data = self.get_trading_signals(symbol)
            signals.append(signal_data)
        return signals

logger.info("✅ MarketAnalyzer loaded")
