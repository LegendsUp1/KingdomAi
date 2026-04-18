#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Market Analysis Module

This module provides market analysis capabilities including price data retrieval,
sentiment analysis, and trading recommendations.
"""

import logging
import sys
import os
import importlib
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger("kingdom_ai")

async def initialize_market_analysis_components(event_bus=None):
    """
    Initialize market analysis components.
    
    Args:
        event_bus: The event bus to connect components to
        
    Returns:
        Dict: Dictionary of initialized components
    """
    logger.info("Initializing market analysis components")
    
    # Components dictionary to return
    components = {}
    
    try:
        # First, try to import the MarketAnalyzer class from root directory
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from market_analyzer_new import MarketAnalyzer
        
        # Create default configuration
        config = {
            "exchanges": {
                "binance": {
                    "api_key": "",
                    "api_secret": "",
                },
                "coinbase": {
                    "api_key": "",
                    "api_secret": "",
                }
            },
            "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
            "market_interval": 60  # seconds
        }
        
        # Create market analyzer instance
        market_analyzer = MarketAnalyzer(config)
        
        # Connect to event bus
        if event_bus:
            market_analyzer.event_bus = event_bus
        
        components["market_analyzer"] = market_analyzer
        logger.info("Market analyzer component initialized")
        
        return components
        
    except Exception as e:
        logger.error(f"Error initializing market_analysis components: {str(e)}")
        return {}
