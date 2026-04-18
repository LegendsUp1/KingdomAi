#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Multi-Market Intelligence Module

This module provides cross-market and cross-asset trading intelligence,
supporting all market types including stocks, bonds, forex, commodities,
cryptocurrencies, and other tradable assets.
"""

import os
import sys
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Union
import json

# Import core modules
from core.base_component import BaseComponent
from core.market_definitions import AssetClass, MarketType, ExchangeType
from core.redis_quantum_manager import RedisQuantumNexus

class MarketIntelligence(BaseComponent):
    """
    Multi-Market Intelligence for Kingdom AI Trading System.
    
    Provides advanced analysis across all market types and asset classes,
    enabling intelligent trading decisions based on cross-market correlations,
    multi-asset arbitrage opportunities, and global market patterns.
    
    Strictly enforces Redis Quantum Nexus connection on port 6380 with
    password 'QuantumNexus2025', with no fallback allowed.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the market intelligence component."""
        super().__init__(event_bus=event_bus)
        
        # Initialize logger
        self.logger = logging.getLogger(f"KingdomAI.{self.__class__.__name__}")
        
        # Configuration parameters
        self.config = config or {}
        
        # Component status
        self.component_name = "market_intelligence"
        self.status = "initializing"
        
        # Initialize Redis connection
        self.redis_nexus = None
        
        # Market data storage
        self.market_data = {}  # Indexed by symbol
        self.correlation_matrix = {}  # Cross-market correlations
        self.arbitrage_opportunities = []  # Cross-market arbitrage
        self.market_signals = {}  # Trading signals by market
        
        # Asset class specific analyzers
        self.analyzers = {
            AssetClass.STOCK: self._analyze_stock_market,
            AssetClass.BOND: self._analyze_bond_market,
            AssetClass.FOREX: self._analyze_forex_market,
            AssetClass.COMMODITY: self._analyze_commodity_market,
            AssetClass.CRYPTOCURRENCY: self._analyze_crypto_market,
            AssetClass.DERIVATIVE: self._analyze_derivative_market,
            AssetClass.ETF: self._analyze_etf_market,
            AssetClass.FUTURE: self._analyze_futures_market,  # Fixed: FUTURE not FUTURES
            AssetClass.OPTION: self._analyze_options_market,  # Fixed: OPTION not OPTIONS
            AssetClass.NFT: self._analyze_nft_market
        }
        
        # Market type specific analyzers
        self.market_analyzers = {
            MarketType.SPOT: self._analyze_spot_market,
            MarketType.MARGIN: self._analyze_margin_market,
            MarketType.FUTURES: self._analyze_futures_market_type,
            MarketType.OPTIONS: self._analyze_options_market_type,
            MarketType.PERPETUAL: self._analyze_perpetual_market,
            MarketType.OTC: self._analyze_otc_market,
            MarketType.DARK_POOL: self._analyze_darkpool_market,  # Fixed: DARK_POOL not DARKPOOL
            # Note: LENDING, AUCTION, PREDICTION not in MarketType enum - commented out
        }
        
        self.logger.info("Market Intelligence initialized")
    
    async def initialize(self, event_bus=None, config=None):
        """
        Initialize the Market Intelligence component.
        
        Sets up Redis Quantum Nexus connection and event subscriptions.
        """
        if event_bus:
            self.event_bus = event_bus
        
        if config:
            self.config = config
        
        self.logger.info("Initializing Market Intelligence...")
        
        # Initialize Redis Quantum Nexus with strict connection requirements
        self.redis_nexus = RedisQuantumNexus()
        connected = await self.redis_nexus.connect()
        
        # Enforce no fallback - system must halt if Redis connection fails
        if not connected:
            self.logger.critical("Redis Quantum Nexus connection failed. System halting as per requirement.")
            sys.exit(1)
        
        self.logger.info("Redis Quantum Nexus connected successfully on port 6380")
        
        # Set up event subscriptions
        self._setup_event_subscriptions()
        
        self.status = "ready"
        self.logger.info("Market Intelligence initialized successfully")
        
        # Publish status
        await self._publish_status()
        
        return True
    
    def _setup_event_subscriptions(self):
        """Set up subscriptions to relevant events on the event bus."""
        if not self.event_bus:
            self.logger.warning("No event bus available. Event subscriptions skipped.")
            return
        
        # Subscribe to market data events
        self.event_bus.subscribe("market_data_update", self._handle_market_data)
        
        # Subscribe to order book events
        self.event_bus.subscribe("order_book_update", self._handle_order_book)
        
        # Subscribe to trade events
        self.event_bus.subscribe("trade_executed", self._handle_trade_executed)
        
        # Subscribe to system events
        self.event_bus.subscribe("system_shutdown", self._handle_system_shutdown)
        
        # Subscribe to analysis request events
        self.event_bus.subscribe("analysis_request", self._handle_analysis_request)
        
        self.logger.info("Event subscriptions set up")
    
    async def _handle_market_data(self, event_data):
        """Handle incoming market data events."""
        symbol = event_data.get("symbol")
        market_type = event_data.get("market_type")
        asset_class = event_data.get("asset_class")
        
        if not all([symbol, market_type, asset_class]):
            self.logger.warning(f"Incomplete market data received: {event_data}")
            return
        
        # Store market data
        self.market_data[symbol] = event_data
        
        # Run appropriate analyzers based on asset class and market type
        await self._run_asset_class_analyzer(asset_class, symbol, event_data)
        await self._run_market_type_analyzer(market_type, symbol, event_data)
        
        # Update cross-market correlations
        await self._update_correlations()
        
        # Check for arbitrage opportunities
        await self._check_arbitrage_opportunities()
    
    async def _run_asset_class_analyzer(self, asset_class, symbol, data):
        """Run the appropriate analyzer for the asset class."""
        if isinstance(asset_class, str):
            try:
                asset_class = AssetClass[asset_class]
            except KeyError:
                self.logger.warning(f"Unknown asset class: {asset_class}")
                return
        
        analyzer = self.analyzers.get(asset_class)
        if analyzer:
            await analyzer(symbol, data)
    
    async def _run_market_type_analyzer(self, market_type, symbol, data):
        """Run the appropriate analyzer for the market type."""
        if isinstance(market_type, str):
            try:
                market_type = MarketType[market_type]
            except KeyError:
                self.logger.warning(f"Unknown market type: {market_type}")
                return
        
        analyzer = self.market_analyzers.get(market_type)
        if analyzer:
            await analyzer(symbol, data)
    
    async def _handle_order_book(self, event_data):
        """Handle order book update events."""
        symbol = event_data.get("symbol")
        if not symbol:
            return
        
        # Analyze order book data
        await self._analyze_order_book(symbol, event_data)
    
    async def _handle_trade_executed(self, event_data):
        """Handle trade executed events."""
        symbol = event_data.get("symbol")
        if not symbol:
            return
        
        # Analyze trade data
        await self._analyze_trade(symbol, event_data)
    
    async def _handle_system_shutdown(self, event_data):
        """Handle system shutdown events."""
        self.logger.info("System shutdown received, cleaning up resources")
        await self.cleanup()
    
    async def _handle_analysis_request(self, event_data):
        """Handle analysis request events."""
        request_type = event_data.get("request_type")
        symbols = event_data.get("symbols", [])
        
        if request_type == "market_analysis":
            results = await self.analyze_markets(symbols)
            await self._publish_analysis_results(results)
        elif request_type == "arbitrage_opportunities":
            results = await self.find_arbitrage_opportunities(symbols)
            await self._publish_arbitrage_opportunities(results)
        elif request_type == "cross_market_correlations":
            results = await self.get_cross_market_correlations(symbols)
            await self._publish_correlation_results(results)
    
    async def cleanup(self):
        """Clean up resources before shutdown."""
        if self.redis_nexus:
            await self.redis_nexus.disconnect()
    
    async def _publish_status(self):
        """Publish status to the event bus."""
        if not self.event_bus:
            return
        
        status = {
            "component": "market_intelligence",
            "status": self.status,
            "timestamp": time.time()
        }
        
        await self.event_bus.publish("component_status", status)
    
    async def analyze_markets(self, symbols=None):
        """
        Analyze markets for the given symbols.
        
        Args:
            symbols: List of symbols to analyze, or None for all
            
        Returns:
            dict: Analysis results by symbol
        """
        if not symbols:
            symbols = list(self.market_data.keys())
        
        results = {}
        for symbol in symbols:
            if symbol in self.market_data:
                results[symbol] = await self._analyze_market(symbol)
        
        return results
    
    async def _analyze_market(self, symbol):
        """
        Analyze a specific market.
        
        Args:
            symbol: Market symbol to analyze
            
        Returns:
            dict: Analysis results
        """
        data = self.market_data.get(symbol, {})
        asset_class = data.get("asset_class")
        market_type = data.get("market_type")
        
        # Run appropriate analyzers
        await self._run_asset_class_analyzer(asset_class, symbol, data)
        await self._run_market_type_analyzer(market_type, symbol, data)
        
        # Get signals
        signals = self.market_signals.get(symbol, {})
        
        return {
            "symbol": symbol,
            "asset_class": asset_class,
            "market_type": market_type,
            "signals": signals,
            "timestamp": time.time()
        }
    
    # SOTA 2026: Base market analysis helper
    def _base_market_analysis(self, symbol, data, market_type):
        """Common market analysis logic for all asset classes."""
        price = data.get('price', 0)
        volume = data.get('volume', 0)
        change_24h = data.get('change_24h', 0)
        
        if price <= 0:
            return None
        
        # Determine trend
        if change_24h > 5:
            trend = 'strong_bullish'
        elif change_24h > 2:
            trend = 'bullish'
        elif change_24h < -5:
            trend = 'strong_bearish'
        elif change_24h < -2:
            trend = 'bearish'
        else:
            trend = 'neutral'
        
        # Calculate momentum
        momentum = change_24h / 100 if change_24h else 0
        
        # Generate signal
        if abs(change_24h) > 5:
            signal = 'buy' if change_24h > 0 else 'sell'
            confidence = min(0.9, abs(change_24h) / 15)
        else:
            signal = 'hold'
            confidence = 0.5
        
        return {
            'symbol': symbol,
            'market_type': market_type,
            'price': price,
            'volume': volume,
            'change_24h': change_24h,
            'trend': trend,
            'momentum': momentum,
            'signal': signal,
            'confidence': confidence,
            'timestamp': time.time()
        }
    
    # Asset class specific analyzers
    async def _analyze_stock_market(self, symbol, data):
        """Analyze stock market data with SOTA 2026 equity analysis."""
        analysis = self._base_market_analysis(symbol, data, 'stock')
        if analysis:
            # Add stock-specific metrics
            analysis['pe_ratio'] = data.get('pe_ratio', 0)
            analysis['market_cap'] = data.get('market_cap', 0)
            analysis['dividend_yield'] = data.get('dividend_yield', 0)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_bond_market(self, symbol, data):
        """Analyze bond market data with SOTA 2026 fixed income analysis."""
        analysis = self._base_market_analysis(symbol, data, 'bond')
        if analysis:
            analysis['yield'] = data.get('yield', 0)
            analysis['duration'] = data.get('duration', 0)
            analysis['credit_rating'] = data.get('credit_rating', 'unknown')
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_forex_market(self, symbol, data):
        """Analyze forex market data with SOTA 2026 FX analysis."""
        analysis = self._base_market_analysis(symbol, data, 'forex')
        if analysis:
            analysis['spread'] = data.get('spread', 0)
            analysis['session'] = data.get('session', 'global')
            analysis['pip_value'] = data.get('pip_value', 0.0001)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_commodity_market(self, symbol, data):
        """Analyze commodity market data with SOTA 2026 commodities analysis."""
        analysis = self._base_market_analysis(symbol, data, 'commodity')
        if analysis:
            analysis['contract_size'] = data.get('contract_size', 0)
            analysis['seasonality'] = data.get('seasonality', 'neutral')
            analysis['inventory_trend'] = data.get('inventory_trend', 'stable')
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_crypto_market(self, symbol, data):
        """Analyze cryptocurrency market data with SOTA 2026 crypto analysis."""
        analysis = self._base_market_analysis(symbol, data, 'crypto')
        if analysis:
            analysis['market_dominance'] = data.get('market_dominance', 0)
            analysis['network_hashrate'] = data.get('network_hashrate', 0)
            analysis['active_addresses'] = data.get('active_addresses', 0)
            analysis['funding_rate'] = data.get('funding_rate', 0)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_derivative_market(self, symbol, data):
        """Analyze derivative market data with SOTA 2026 derivatives analysis."""
        analysis = self._base_market_analysis(symbol, data, 'derivative')
        if analysis:
            analysis['underlying'] = data.get('underlying', symbol)
            analysis['delta'] = data.get('delta', 0)
            analysis['gamma'] = data.get('gamma', 0)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_etf_market(self, symbol, data):
        """Analyze ETF market data with SOTA 2026 ETF analysis."""
        analysis = self._base_market_analysis(symbol, data, 'etf')
        if analysis:
            analysis['nav'] = data.get('nav', 0)
            analysis['premium_discount'] = data.get('premium_discount', 0)
            analysis['expense_ratio'] = data.get('expense_ratio', 0)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_futures_market(self, symbol, data):
        """Analyze futures market data with SOTA 2026 futures analysis."""
        analysis = self._base_market_analysis(symbol, data, 'futures')
        if analysis:
            analysis['open_interest'] = data.get('open_interest', 0)
            analysis['expiry'] = data.get('expiry', '')
            analysis['basis'] = data.get('basis', 0)
            analysis['contango'] = data.get('basis', 0) > 0
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_options_market(self, symbol, data):
        """Analyze options market data with SOTA 2026 options analysis."""
        analysis = self._base_market_analysis(symbol, data, 'options')
        if analysis:
            analysis['implied_volatility'] = data.get('implied_volatility', 0)
            analysis['strike'] = data.get('strike', 0)
            analysis['expiry'] = data.get('expiry', '')
            analysis['option_type'] = data.get('option_type', 'call')
            analysis['greeks'] = {
                'delta': data.get('delta', 0),
                'gamma': data.get('gamma', 0),
                'theta': data.get('theta', 0),
                'vega': data.get('vega', 0)
            }
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_nft_market(self, symbol, data):
        """Analyze NFT market data with SOTA 2026 NFT analysis."""
        analysis = self._base_market_analysis(symbol, data, 'nft')
        if analysis:
            analysis['floor_price'] = data.get('floor_price', 0)
            analysis['unique_holders'] = data.get('unique_holders', 0)
            analysis['total_supply'] = data.get('total_supply', 0)
            analysis['rarity_score'] = data.get('rarity_score', 0)
            self.market_signals[symbol] = analysis
        return analysis
    
    # Market type specific analyzers
    async def _analyze_spot_market(self, symbol, data):
        """Analyze spot market data with SOTA 2026 spot analysis."""
        analysis = self._base_market_analysis(symbol, data, 'spot')
        if analysis:
            analysis['liquidity_score'] = min(1.0, data.get('volume', 0) / 1000000)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_margin_market(self, symbol, data):
        """Analyze margin market data with SOTA 2026 margin analysis."""
        analysis = self._base_market_analysis(symbol, data, 'margin')
        if analysis:
            analysis['max_leverage'] = data.get('max_leverage', 10)
            analysis['margin_ratio'] = data.get('margin_ratio', 0)
            analysis['liquidation_price'] = data.get('liquidation_price', 0)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_futures_market_type(self, symbol, data):
        """Analyze futures market type data with SOTA 2026 analysis."""
        return await self._analyze_futures_market(symbol, data)
    
    async def _analyze_options_market_type(self, symbol, data):
        """Analyze options market type data with SOTA 2026 analysis."""
        return await self._analyze_options_market(symbol, data)
    
    async def _analyze_perpetual_market(self, symbol, data):
        """Analyze perpetual market data with SOTA 2026 perpetuals analysis."""
        analysis = self._base_market_analysis(symbol, data, 'perpetual')
        if analysis:
            analysis['funding_rate'] = data.get('funding_rate', 0)
            analysis['funding_interval'] = data.get('funding_interval', 8)  # hours
            analysis['index_price'] = data.get('index_price', 0)
            analysis['mark_price'] = data.get('mark_price', 0)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_lending_market(self, symbol, data):
        """Analyze lending market data with SOTA 2026 DeFi analysis."""
        analysis = self._base_market_analysis(symbol, data, 'lending')
        if analysis:
            analysis['supply_apy'] = data.get('supply_apy', 0)
            analysis['borrow_apy'] = data.get('borrow_apy', 0)
            analysis['utilization'] = data.get('utilization', 0)
            analysis['total_supply'] = data.get('total_supply', 0)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_otc_market(self, symbol, data):
        """Analyze OTC market data with SOTA 2026 OTC analysis."""
        analysis = self._base_market_analysis(symbol, data, 'otc')
        if analysis:
            analysis['min_order_size'] = data.get('min_order_size', 0)
            analysis['settlement_time'] = data.get('settlement_time', 'T+2')
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_auction_market(self, symbol, data):
        """Analyze auction market data with SOTA 2026 auction analysis."""
        analysis = self._base_market_analysis(symbol, data, 'auction')
        if analysis:
            analysis['auction_type'] = data.get('auction_type', 'open')
            analysis['clearing_price'] = data.get('clearing_price', 0)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_darkpool_market(self, symbol, data):
        """Analyze dark pool market data with SOTA 2026 dark pool analysis."""
        analysis = self._base_market_analysis(symbol, data, 'darkpool')
        if analysis:
            analysis['hidden_liquidity'] = data.get('hidden_liquidity', 0)
            analysis['avg_trade_size'] = data.get('avg_trade_size', 0)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_prediction_market(self, symbol, data):
        """Analyze prediction market data with SOTA 2026 prediction analysis."""
        analysis = self._base_market_analysis(symbol, data, 'prediction')
        if analysis:
            analysis['probability'] = data.get('probability', 0.5)
            analysis['resolution_date'] = data.get('resolution_date', '')
            analysis['total_stakes'] = data.get('total_stakes', 0)
            self.market_signals[symbol] = analysis
        return analysis
    
    async def _analyze_order_book(self, symbol, data):
        """Analyze order book data with SOTA 2026 microstructure analysis."""
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        if not bids or not asks:
            return None
        
        # Calculate order book metrics
        bid_volume = sum(b[1] for b in bids[:20]) if bids else 0
        ask_volume = sum(a[1] for a in asks[:20]) if asks else 0
        total_volume = bid_volume + ask_volume
        
        imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0
        spread = (asks[0][0] - bids[0][0]) / bids[0][0] if bids and asks else 0
        
        analysis = {
            'symbol': symbol,
            'bid_volume': bid_volume,
            'ask_volume': ask_volume,
            'imbalance': imbalance,
            'spread': spread,
            'depth_10': total_volume,
            'signal': 'buy' if imbalance > 0.2 else ('sell' if imbalance < -0.2 else 'neutral'),
            'timestamp': time.time()
        }
        
        self.market_signals[f"{symbol}_orderbook"] = analysis
        return analysis
    
    async def _analyze_trade(self, symbol, data):
        """Analyze trade data with SOTA 2026 trade flow analysis."""
        price = data.get('price', 0)
        size = data.get('size', 0)
        side = data.get('side', 'unknown')
        
        if price <= 0:
            return None
        
        analysis = {
            'symbol': symbol,
            'price': price,
            'size': size,
            'side': side,
            'notional': price * size,
            'is_large': size > data.get('avg_size', size) * 5,
            'timestamp': time.time()
        }
        
        self.market_signals[f"{symbol}_trade"] = analysis
        return analysis
    
    async def _update_correlations(self):
        """Update cross-market correlations with SOTA 2026 correlation analysis."""
        try:
            symbols = list(self.market_signals.keys())
            if len(symbols) < 2:
                return
            
            # Calculate pairwise correlations based on price changes
            for i, sym1 in enumerate(symbols[:10]):  # Limit to prevent O(n^2) explosion
                for sym2 in symbols[i+1:10]:
                    data1 = self.market_signals.get(sym1, {})
                    data2 = self.market_signals.get(sym2, {})
                    
                    change1 = data1.get('change_24h', 0)
                    change2 = data2.get('change_24h', 0)
                    
                    # Simple correlation proxy based on directional alignment
                    if change1 * change2 > 0:  # Same direction
                        correlation = 0.5 + min(0.5, abs(change1 - change2) / 20)
                    else:  # Opposite direction
                        correlation = -0.5 - min(0.5, abs(change1 + change2) / 20)
                    
                    self.cross_market_correlations[f"{sym1}_{sym2}"] = {
                        'correlation': correlation,
                        'timestamp': time.time()
                    }
                    
        except Exception as e:
            logging.error(f"Error updating correlations: {e}")
    
    async def _check_arbitrage_opportunities(self):
        """Check for arbitrage opportunities with SOTA 2026 cross-market analysis."""
        try:
            self.arbitrage_opportunities = []
            
            # Check for price discrepancies across markets
            symbols_by_base = {}
            for symbol, data in self.market_signals.items():
                if '_' in symbol:  # Skip derived signals
                    continue
                base = symbol.split('/')[0] if '/' in symbol else symbol[:3]
                if base not in symbols_by_base:
                    symbols_by_base[base] = []
                symbols_by_base[base].append((symbol, data))
            
            # Find price differences for same base asset
            for base, pairs in symbols_by_base.items():
                if len(pairs) < 2:
                    continue
                
                prices = [(s, d.get('price', 0)) for s, d in pairs if d.get('price', 0) > 0]
                if len(prices) < 2:
                    continue
                
                min_price = min(prices, key=lambda x: x[1])
                max_price = max(prices, key=lambda x: x[1])
                
                spread = (max_price[1] - min_price[1]) / min_price[1] if min_price[1] > 0 else 0
                
                if spread > 0.005:  # 0.5% minimum spread
                    self.arbitrage_opportunities.append({
                        'base_asset': base,
                        'buy_from': min_price[0],
                        'buy_price': min_price[1],
                        'sell_to': max_price[0],
                        'sell_price': max_price[1],
                        'spread': spread,
                        'potential_profit_pct': spread * 100,
                        'timestamp': time.time()
                    })
                    
        except Exception as e:
            logging.error(f"Error checking arbitrage: {e}")
    
    async def find_arbitrage_opportunities(self, symbols=None):
        """
        Find arbitrage opportunities for the given symbols.
        
        Args:
            symbols: List of symbols to analyze, or None for all
            
        Returns:
            list: Arbitrage opportunities
        """
        # Implementation for finding arbitrage opportunities
        return self.arbitrage_opportunities
    
    async def get_cross_market_correlations(self, symbols=None):
        """
        Get cross-market correlations for the given symbols.
        
        Args:
            symbols: List of symbols to analyze, or None for all
            
        Returns:
            dict: Correlation matrix
        """
        # Implementation for getting cross-market correlations
        return self.correlation_matrix
    
    async def _publish_analysis_results(self, results):
        """Publish analysis results to the event bus."""
        if not self.event_bus:
            return
        
        await self.event_bus.publish("market_analysis_results", results)
    
    async def _publish_arbitrage_opportunities(self, opportunities):
        """Publish arbitrage opportunities to the event bus."""
        if not self.event_bus:
            return
        
        await self.event_bus.publish("arbitrage_opportunities", opportunities)
    
    async def _publish_correlation_results(self, correlations):
        """Publish correlation results to the event bus."""
        if not self.event_bus:
            return
        
        await self.event_bus.publish("cross_market_correlations", correlations)
