"""Portfolio analytics module for Kingdom AI."""

import logging
import asyncio
import traceback as tb
import types
import sys
from typing import Dict, Any, Optional, List

# Initialize global bus reference and module references to avoid reference errors
# These will be replaced by the launcher if needed
bus = None
event_bus = None
traceback = tb  # Ensure traceback is accessible

# Setup logger
logger = logging.getLogger("kingdom_ai.portfolio_analytics")

HAS_FIX_MODULES = False


# Define fallback classes in case fix modules are not available
class FallbackRiskAssessmentCore:
    """Fallback risk assessment core."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.portfolio_analytics")
    
    async def handle_analysis_request(self, event_type, data):
        self.logger.info(f"Handling risk analysis request (fallback): {data}")
        return {"status": "error", "message": "Risk assessment not available in fallback mode"}


class FallbackPerformanceMetricsCore:
    """Fallback performance metrics core."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.portfolio_analytics")
    
    async def handle_analysis_request(self, event_type, data):
        self.logger.info(f"Handling performance analysis request (fallback): {data}")
        return {"status": "error", "message": "Performance metrics not available in fallback mode"}


class FallbackAllocationOptimizerCore:
    """Fallback allocation optimizer core."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.portfolio_analytics")
    
    async def handle_optimization_request(self, event_type, data):
        self.logger.info(f"Handling optimization request (fallback): {data}")
        return {"status": "error", "message": "Allocation optimization not available in fallback mode"}


class FallbackPortfolioReportGenerator:
    """Fallback portfolio report generator."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logging.getLogger("kingdom_ai.portfolio_analytics")
    
    async def handle_report_request(self, event_type, data):
        self.logger.info(f"Handling report generation request (fallback): {data}")
        return {"status": "error", "message": "Report generation not available in fallback mode"}


async def initialize_portfolio_analytics_components(event_bus):
    """Initialize portfolio analytics components and connect to event bus.
    
    Args:
        event_bus: Event bus to connect components to
        
    Returns:
        Dictionary of initialized components
    """
    components = {}
    
    try:
        logger.info("Initializing portfolio analytics components")
        
        if HAS_FIX_MODULES:
            # Initialize from fix modules
            logger.info("Using portfolio analytics fix modules")
            
            # Create risk assessment core
            risk_assessment = RiskAssessmentCore()
            components["risk_assessment"] = risk_assessment
            
            # Create performance metrics core
            perf_metrics = PerformanceMetricsCore()
            components["performance_metrics"] = perf_metrics
            
            # Create allocation optimizer core
            allocation_optimizer = AllocationOptimizerCore()
            components["allocation_optimizer"] = allocation_optimizer
            
            # Create portfolio report generator
            report_generator = PortfolioReportGenerator()
            components["report_generator"] = report_generator
            
            # Register event handlers with event bus
            if event_bus:
                # Risk assessment events
                event_bus.register_handler("portfolio.analyze.risk", 
                                          risk_assessment.calculate_var)
                event_bus.register_handler("portfolio.analyze.stress", 
                                          risk_assessment.run_stress_test)
                
                # Performance metrics events
                event_bus.register_handler("portfolio.analyze.performance", 
                                          perf_metrics.calculate_performance)
                event_bus.register_handler("portfolio.analyze.attribution", 
                                          perf_metrics.calculate_attribution)
                
                # Allocation optimizer events
                event_bus.register_handler("portfolio.optimize.allocation", 
                                          allocation_optimizer.optimize_portfolio)
                
                # Report generator events
                event_bus.register_handler("portfolio.generate.report", 
                                          report_generator.generate_report)
                
                logger.info("Registered portfolio analytics event handlers")
        else:
            # Initialize with fallback classes
            logger.info("Using portfolio analytics fallback implementations")
            
            # Create fallback components
            risk_assessment = FallbackRiskAssessmentCore(event_bus=event_bus)
            components["risk_assessment"] = risk_assessment
            
            perf_metrics = FallbackPerformanceMetricsCore(event_bus=event_bus)
            components["performance_metrics"] = perf_metrics
            
            allocation_optimizer = FallbackAllocationOptimizerCore(event_bus=event_bus)
            components["allocation_optimizer"] = allocation_optimizer
            
            report_generator = FallbackPortfolioReportGenerator(event_bus=event_bus)
            components["report_generator"] = report_generator
            
            # Add register_handler method if it doesn't exist (EventBus compatibility adapter)
            if event_bus and not hasattr(event_bus, 'register_handler'):
                # Create an adapter method to handle different EventBus implementations
                def register_handler_adapter(self, event_type, handler):
                    # Use the subscribe method instead if it exists
                    if hasattr(self, 'subscribe'):
                        return self.subscribe(event_type, handler)
                    # Fallback to another method like register if available
                    elif hasattr(self, 'register'):
                        return self.register(event_type, handler)
                    # Fallback to any other event registration method with similar patterns
                    elif hasattr(self, 'add_listener'):
                        return self.add_listener(event_type, handler)
                    elif hasattr(self, 'on'):
                        return self.on(event_type, handler)
                    # Log error if no compatible method is found
                    else:
                        logger.error("EventBus has no compatible subscription method")
                        return False
                
                # Dynamically add the adapter method to the event_bus instance
                import types
                event_bus.register_handler = types.MethodType(register_handler_adapter, event_bus)
            
            # Register event handlers with event bus
            if event_bus:
                try:
                    # Risk assessment events
                    event_bus.register_handler("portfolio.analyze.risk", 
                                              risk_assessment.handle_analysis_request)
                    event_bus.register_handler("portfolio.analyze.stress", 
                                              risk_assessment.handle_analysis_request)
                    
                    # Performance metrics events
                    event_bus.register_handler("portfolio.analyze.performance", 
                                              perf_metrics.handle_analysis_request)
                    event_bus.register_handler("portfolio.analyze.attribution", 
                                              perf_metrics.handle_analysis_request)
                    
                    # Allocation optimizer events
                    event_bus.register_handler("portfolio.optimize.allocation", 
                                              allocation_optimizer.handle_optimization_request)
                except Exception as e:
                    import traceback
                    logger.error(f"Error registering event handlers: {e}")
                    logger.error(traceback.format_exc())
                
                # Report generator events
                event_bus.register_handler("portfolio.generate.report", 
                                          report_generator.handle_report_request)
                
                logger.info("Registered portfolio analytics fallback event handlers")
        
        logger.info("Portfolio analytics components initialized")
    except Exception as e:
        logger.error(f"Error initializing portfolio analytics components: {e}")
        logger.error(traceback.format_exc())
    
    return components
