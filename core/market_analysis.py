#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Market Analysis component for Kingdom AI.

This module connects existing market analysis components to the event bus.
"""

import logging
import os
import sys

# Import existing market analysis components
try:
    from ..backup_fixed_files.market_analyzer import MarketAnalyzer
    from ..backup_fixed_files.market_analyzer_new import MarketAnalyzerNew
    from ..kingdom_market_data_core import MarketDataCore
    MARKET_COMPONENTS_AVAILABLE = True
except ImportError:
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from backup_fixed_files.market_analyzer import MarketAnalyzer
        try:
            from backup_fixed_files.market_analyzer_new import MarketAnalyzerNew
        except ImportError:
            MarketAnalyzerNew = None
        try:
            from kingdom_market_data_core import MarketDataCore
        except ImportError:
            MarketDataCore = None
        MARKET_COMPONENTS_AVAILABLE = True
    except ImportError:
        MARKET_COMPONENTS_AVAILABLE = False

# Import existing market data components
try:
    from ..core.market_api import MarketAPI
    from ..core.market_data_streaming import MarketDataStreamer
    from ..core.market_stream import MarketStream
    MARKET_DATA_AVAILABLE = True
except ImportError:
    try:
        from market_api import MarketAPI
        from market_data_streaming import MarketDataStreamer
        from market_stream import MarketStream
        MARKET_DATA_AVAILABLE = True
    except ImportError:
        MARKET_DATA_AVAILABLE = False

from core.base_component import BaseComponent

# Set up logger
logger = logging.getLogger("kingdom_ai")

# Initialization function that 4keys.py expects
async def initialize_market_analysis_components(event_bus):
    """
    Initialize market analysis components and connect them to the event bus.
    
    Args:
        event_bus: Event bus instance for component communication
        
    Returns:
        Dictionary of initialized components
    """
    logger.info("Initializing market analysis components")
    components = {}
    
    try:
        # Initialize market analyzer components
        if MARKET_COMPONENTS_AVAILABLE:
            # Market Analyzer
            market_analyzer = MarketAnalyzer()
            components["market_analyzer"] = market_analyzer
            
            # Market Analyzer New (if available)
            if MarketAnalyzerNew:
                market_analyzer_new = MarketAnalyzerNew()
                components["market_analyzer_new"] = market_analyzer_new
            
            # Market Data Core (if available)
            if MarketDataCore:
                market_data_core = MarketDataCore(event_bus=event_bus)
                components["market_data_core"] = market_data_core
            
            logger.info("Market analysis components initialized")
        else:
            logger.warning("Market analysis components not available, using fallbacks")
            
            # Create fallback market analyzer
            class FallbackMarketAnalyzer(BaseComponent):
                def __init__(self, event_bus):
                    super().__init__(event_bus=event_bus)
                    self.name = "FallbackMarketAnalyzer"
                
                async def analyze_market(self, event_type, data):
                    symbol = data.get("symbol", "BTCUSD")
                    timeframe = data.get("timeframe", "1h")
                    return {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "trend": "neutral",
                        "signals": [],
                        "indicators": {
                            "sma": {"short": 0, "medium": 0, "long": 0},
                            "rsi": 50,
                            "bollinger": {"upper": 0, "middle": 0, "lower": 0}
                        }
                    }
                    
                async def get_indicators(self, event_type, data):
                    symbol = data.get("symbol", "BTCUSD")
                    indicators = data.get("indicators", ["sma", "rsi"])
                    result = {}
                    if "sma" in indicators:
                        result["sma"] = {"short": 0, "medium": 0, "long": 0}
                    if "rsi" in indicators:
                        result["rsi"] = 50
                    return {"symbol": symbol, "indicators": result}
            
            # Create fallback analyzer
            fallback_analyzer = FallbackMarketAnalyzer(event_bus=event_bus)
            components["market_analyzer"] = fallback_analyzer
            
        # Initialize market data components
        if MARKET_DATA_AVAILABLE:
            # Market API
            market_api = MarketAPI()
            components["market_api"] = market_api
            
            # Market Data Streamer
            market_data_streamer = MarketDataStreamer(event_bus=event_bus)
            components["market_data_streamer"] = market_data_streamer
            
            # Market Stream
            market_stream = MarketStream(event_bus=event_bus)
            components["market_stream"] = market_stream
            
            logger.info("Market data components initialized")
        
        # Register event handlers for market components
        if hasattr(event_bus, 'register_handler'):
            # Core market analysis handlers
            if "market_analyzer" in components:
                event_bus.register_handler("market.analyze", components["market_analyzer"].analyze_market)
                event_bus.register_handler("market.indicators", components["market_analyzer"].get_indicators)
                
            # Market data handlers if available
            if "market_data_streamer" in components:
                event_bus.register_handler("market.stream_data", components["market_data_streamer"].start_streaming)
                event_bus.register_handler("market.stop_stream", components["market_data_streamer"].stop_streaming)
                
            # Market stream handlers if available
            if "market_stream" in components:
                event_bus.register_handler("market.subscribe", components["market_stream"].subscribe)
                event_bus.register_handler("market.unsubscribe", components["market_stream"].unsubscribe)
                
        elif hasattr(event_bus, 'subscribe'):
            # Core market analysis handlers
            if "market_analyzer" in components:
                event_bus.subscribe("market.analyze", components["market_analyzer"].analyze_market)
                event_bus.subscribe("market.indicators", components["market_analyzer"].get_indicators)
                
            # Market data handlers if available
            if "market_data_streamer" in components:
                event_bus.subscribe("market.stream_data", components["market_data_streamer"].start_streaming)
                event_bus.subscribe("market.stop_stream", components["market_data_streamer"].stop_streaming)
                
            # Market stream handlers if available
            if "market_stream" in components:
                event_bus.subscribe("market.subscribe", components["market_stream"].subscribe)
                event_bus.subscribe("market.unsubscribe", components["market_stream"].unsubscribe)
        
        # Initialize all components that support initialization
        for component_name, component in components.items():
            if hasattr(component, 'initialize'):
                try:
                    await component.initialize()
                except Exception as e:
                    logger.error(f"Error initializing {component_name}: {e}")
            
            # Mark as initialized for components with that attribute
            if hasattr(component, 'initialized'):
                component.initialized = True
                
        logger.info(f"Market analysis components initialized with {len(components)} components")
    except Exception as e:
        logger.error(f"Error initializing market analysis components: {e}")
    
    return components
