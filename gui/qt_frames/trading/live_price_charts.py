#!/usr/bin/env python3
"""
LIVE Price Charts - Real OHLCV Data from Exchanges
Fetches real candlestick data and renders live charts
NO MOCK DATA - 100% LIVE
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)


class LivePriceCharts:
    """
    LIVE Price Charts with Real OHLCV Data
    Fetches candlestick data from exchanges
    """
    
    def __init__(self, exchange_name: str = 'binance', api_keys: Optional[Dict] = None):
        """
        Initialize live price charts.
        
        Args:
            exchange_name: Exchange to use
            api_keys: API keys (optional)
        """
        import ccxt
        
        self.exchange_name = exchange_name
        self.api_keys = api_keys or {}
        self.chart_data: Dict[str, List] = {}  # symbol -> OHLCV data
        
        try:
            exchange_class = getattr(ccxt, exchange_name)
            config = {'enableRateLimit': True}
            
            if f'{exchange_name}' in api_keys:
                config['apiKey'] = api_keys.get(f'{exchange_name}')
                config['secret'] = api_keys.get(f'{exchange_name}_secret')
            
            self.exchange = exchange_class(config)
            logger.info(f"✅ Price charts initialized: {exchange_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize price charts: {e}")
            self.exchange = None
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1h',
        limit: int = 100
    ) -> List[List]:
        """
        Fetch real OHLCV data from exchange.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candlestick timeframe ('1m', '5m', '1h', '1d', etc.)
            limit: Number of candles
            
        Returns:
            List of OHLCV candles: [[timestamp, open, high, low, close, volume], ...]
        """
        if not self.exchange:
            logger.error("Exchange not initialized")
            return []
        
        try:
            # Fetch OHLCV data
            ohlcv = await asyncio.to_thread(
                self.exchange.fetch_ohlcv,
                symbol,
                timeframe,
                limit=limit
            )
            
            # Store in memory
            self.chart_data[symbol] = ohlcv
            
            logger.info(f"✅ Fetched {len(ohlcv)} candles for {symbol} ({timeframe})")
            return ohlcv
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            return []
    
    def get_chart_data(self, symbol: str) -> List[List]:
        """Get cached chart data for symbol."""
        return self.chart_data.get(symbol, [])
    
    def calculate_indicators(self, symbol: str) -> Dict:
        """
        Calculate technical indicators from OHLCV data.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Dictionary of indicators (SMA, EMA, RSI, etc.)
        """
        ohlcv = self.chart_data.get(symbol, [])
        if not ohlcv or len(ohlcv) < 14:
            return {}
        
        # Extract close prices
        closes = np.array([candle[4] for candle in ohlcv])
        
        indicators = {}
        
        try:
            # Simple Moving Average (20 period)
            if len(closes) >= 20:
                sma_20 = np.mean(closes[-20:])
                indicators['sma_20'] = float(sma_20)
            
            # Exponential Moving Average (20 period)
            if len(closes) >= 20:
                ema_20 = self._calculate_ema(closes, 20)
                indicators['ema_20'] = float(ema_20)
            
            # RSI (14 period)
            if len(closes) >= 14:
                rsi = self._calculate_rsi(closes, 14)
                indicators['rsi_14'] = float(rsi)
            
            # Bollinger Bands
            if len(closes) >= 20:
                bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(closes, 20, 2)
                indicators['bb_upper'] = float(bb_upper)
                indicators['bb_middle'] = float(bb_middle)
                indicators['bb_lower'] = float(bb_lower)
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
        
        return indicators
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average."""
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_bollinger_bands(
        self,
        prices: np.ndarray,
        period: int = 20,
        std_dev: float = 2.0
    ) -> tuple:
        """Calculate Bollinger Bands."""
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        return upper_band, sma, lower_band
