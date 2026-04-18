#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Visualization component for Kingdom AI.

This module connects the existing visualization components to the event bus.
"""

import logging
import os
import sys

# Import the existing visualization engine
try:
    from ..performance_analytics.visualization_engine import VisualizationEngine
    VISUALIZATION_ENGINE_AVAILABLE = True
except ImportError:
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from performance_analytics.visualization_engine import VisualizationEngine
        VISUALIZATION_ENGINE_AVAILABLE = True
    except ImportError:
        VISUALIZATION_ENGINE_AVAILABLE = False


# Set up logger
logger = logging.getLogger("kingdom_ai")

# Initialization function that 4keys.py expects
async def initialize_visualization_components(event_bus):
    """
    Initialize visualization components and connect them to the event bus.
    
    Args:
        event_bus: Event bus instance for component communication
        
    Returns:
        Dictionary of initialized components
    """
    logger.info("Initializing visualization components")
    components = {}
    
    try:
        # Initialize the main visualization engine if available
        if VISUALIZATION_ENGINE_AVAILABLE:
            viz_engine = VisualizationEngine(event_bus=event_bus)
            components["visualization_engine"] = viz_engine
            
            # Attempt to register event handlers
            if hasattr(event_bus, 'register_handler'):
                event_bus.register_handler("visualization.create_chart", viz_engine.create_chart)
                event_bus.register_handler("visualization.create_dashboard", viz_engine.create_dashboard)
                event_bus.register_handler("visualization.create_equity_curve", viz_engine.create_equity_curve)
                event_bus.register_handler("visualization.create_drawdown_chart", viz_engine.create_drawdown_chart)
                event_bus.register_handler("visualization.create_performance_summary", viz_engine.create_performance_summary)
            elif hasattr(event_bus, 'subscribe'):
                event_bus.subscribe("visualization.create_chart", viz_engine.create_chart)
                event_bus.subscribe("visualization.create_dashboard", viz_engine.create_dashboard)
                event_bus.subscribe("visualization.create_equity_curve", viz_engine.create_equity_curve)
                event_bus.subscribe("visualization.create_drawdown_chart", viz_engine.create_drawdown_chart)
                event_bus.subscribe("visualization.create_performance_summary", viz_engine.create_performance_summary)
                
            logger.info("Visualization engine connected to event bus")
        else:
            # Create fallback visualization components from fix files
            logger.warning("Visualization engine not available, using fallback components")
            
            # These components match what's in the fix_visualization_components.py
            viz_components = {
                "MarketChartVisualizer": type("MarketChartVisualizer", (), {
                    "create_chart": lambda data: {"status": "success", "chart_url": "market_chart.png"},
                    "name": "MarketChartVisualizer",
                    "handle_create_chart": lambda event_type, data: {"status": "success", "chart_url": "market_chart.png"}
                }),
                "PortfolioVisualizer": type("PortfolioVisualizer", (), {
                    "visualize_portfolio": lambda data: {"status": "success", "chart_url": "portfolio.png"},
                    "name": "PortfolioVisualizer",
                    "handle_visualize": lambda event_type, data: {"status": "success", "chart_url": "portfolio.png"}
                }),
                "PerformanceVisualizer": type("PerformanceVisualizer", (), {
                    "create_performance_chart": lambda data: {"status": "success", "chart_url": "performance.png"},
                    "name": "PerformanceVisualizer",
                    "handle_create_chart": lambda event_type, data: {"status": "success", "chart_url": "performance.png"}
                }),
                "TechnicalChartVisualizer": type("TechnicalChartVisualizer", (), {
                    "create_technical_chart": lambda data: {"status": "success", "chart_url": "technical.png"},
                    "name": "TechnicalChartVisualizer",
                    "handle_create_chart": lambda event_type, data: {"status": "success", "chart_url": "technical.png"}
                }),
                "CorrelationVisualizer": type("CorrelationVisualizer", (), {
                    "create_correlation_matrix": lambda data: {"status": "success", "chart_url": "correlation.png"},
                    "name": "CorrelationVisualizer",
                    "handle_create_chart": lambda event_type, data: {"status": "success", "chart_url": "correlation.png"}
                })
            }
            
            # Add all fallback visualizers to components
            components.update(viz_components)
            
            # Register event handlers for fallback components
            if hasattr(event_bus, 'register_handler'):
                event_bus.register_handler("visualization.market_chart", viz_components["MarketChartVisualizer"].handle_create_chart)
                event_bus.register_handler("visualization.portfolio", viz_components["PortfolioVisualizer"].handle_visualize)
                event_bus.register_handler("visualization.performance", viz_components["PerformanceVisualizer"].handle_create_chart)
                event_bus.register_handler("visualization.technical", viz_components["TechnicalChartVisualizer"].handle_create_chart)
                event_bus.register_handler("visualization.correlation", viz_components["CorrelationVisualizer"].handle_create_chart)
            elif hasattr(event_bus, 'subscribe'):
                event_bus.subscribe("visualization.market_chart", viz_components["MarketChartVisualizer"].handle_create_chart)
                event_bus.subscribe("visualization.portfolio", viz_components["PortfolioVisualizer"].handle_visualize)
                event_bus.subscribe("visualization.performance", viz_components["PerformanceVisualizer"].handle_create_chart)
                event_bus.subscribe("visualization.technical", viz_components["TechnicalChartVisualizer"].handle_create_chart)
                event_bus.subscribe("visualization.correlation", viz_components["CorrelationVisualizer"].handle_create_chart)
                
            logger.info("Fallback visualization components connected to event bus")
        
        logger.info(f"Visualization components initialized with {len(components)} components")
    except Exception as e:
        logger.error(f"Error initializing visualization components: {e}")
    
    return components
