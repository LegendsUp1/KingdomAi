#!/usr/bin/env python3
"""
Kingdom AI Trading Binder Module

This module implements the binding mechanism for connecting trading components
to the event bus and handling trading-specific events and state updates.
"""

import logging
import traceback
from datetime import datetime
import threading
import time
import json

logger = logging.getLogger("KingdomAI.TradingBinder")

class TradingBinder:
    """
    Trading components binding mechanism.
    
    This class manages the connections between trading GUI components and 
    the trading system backend, ensuring that trading data flows correctly
    between the UI and the trading engine.
    """
    
    def __init__(self, event_bus=None, gui_binder=None):
        """Initialize the trading binder"""
        self.event_bus = event_bus
        self.gui_binder = gui_binder
        self.trading_components = {}
        self.market_data = {}
        self.current_orders = {}
        self.portfolio = {}
        self.trading_enabled = False
        
        # Event types that this binder handles
        self.event_types = [
            "trading.market_data",
            "trading.order_update",
            "trading.portfolio_update",
            "trading.status",
            "trading.error"
        ]
        
        self.logger = logger
        self.logger.info("Trading Binder initialized")
    
    def start(self):
        """Start the trading binder"""
        # Register with the event bus
        if self.event_bus:
            self._register_event_handlers()
        
        self.logger.info("Trading Binder started")
    
    def register_component(self, component_id, component, event_types=None):
        """Register a trading component with the binder"""
        self.trading_components[component_id] = {
            "component": component,
            "event_types": event_types or []
        }
        
        # Also register with the main GUI binder if available
        if self.gui_binder and hasattr(self.gui_binder, "register_component"):
            self.gui_binder.register_component(component_id, component, event_types)
        
        self.logger.info(f"Registered trading component: {component_id}")
        
        # If we already have data that this component needs, update it immediately
        self._update_component_with_existing_data(component_id, component)
        
        # Return the component ID for reference
        return component_id
    
    def _update_component_with_existing_data(self, component_id, component):
        """Update a component with existing data"""
        component_info = self.trading_components[component_id]
        event_types = component_info["event_types"]
        
        # Check if component is interested in market data
        if "trading.market_data" in event_types and self.market_data:
            if hasattr(component, "update_market_data"):
                component.update_market_data(self.market_data)
            elif hasattr(component, "update_from_event"):
                component.update_from_event("trading.market_data", {"data": self.market_data})
        
        # Check if component is interested in order updates
        if "trading.order_update" in event_types and self.current_orders:
            if hasattr(component, "update_orders"):
                component.update_orders(self.current_orders)
            elif hasattr(component, "update_from_event"):
                component.update_from_event("trading.order_update", {"orders": self.current_orders})
        
        # Check if component is interested in portfolio updates
        if "trading.portfolio_update" in event_types and self.portfolio:
            if hasattr(component, "update_portfolio"):
                component.update_portfolio(self.portfolio)
            elif hasattr(component, "update_from_event"):
                component.update_from_event("trading.portfolio_update", {"portfolio": self.portfolio})
    
    def _register_event_handlers(self):
        """Register all event handlers with the event bus"""
        if not self.event_bus:
            self.logger.warning("Cannot register event handlers: No event bus available")
            return
        
        # Register handlers for all trading event types
        for event_type in self.event_types:
            self.event_bus.subscribe(event_type, self._handle_event)
        
        self.logger.info(f"Registered event handlers for trading events")
    
    def _handle_event(self, event_type, data):
        """Handle a trading event from the event bus"""
        try:
            # Handle different event types
            if event_type == "trading.market_data":
                self._handle_market_data(data)
            elif event_type == "trading.order_update":
                self._handle_order_update(data)
            elif event_type == "trading.portfolio_update":
                self._handle_portfolio_update(data)
            elif event_type == "trading.status":
                self._handle_trading_status(data)
            elif event_type == "trading.error":
                self._handle_trading_error(data)
            
            # Update components that are interested in this event type
            self._update_components_for_event(event_type, data)
            
            self.logger.debug(f"Handled trading event: {event_type}")
        except Exception as e:
            self.logger.error(f"Error handling trading event {event_type}: {e}")
            self.logger.error(traceback.format_exc())
    
    def _handle_market_data(self, data):
        """Handle market data updates"""
        market_data = data.get("data", {})
        if market_data:
            # Update our cached market data
            self.market_data.update(market_data)
    
    def _handle_order_update(self, data):
        """Handle order updates"""
        orders = data.get("orders", {})
        if orders:
            # Update our cached orders
            self.current_orders = orders
    
    def _handle_portfolio_update(self, data):
        """Handle portfolio updates"""
        portfolio = data.get("portfolio", {})
        if portfolio:
            # Update our cached portfolio
            self.portfolio = portfolio
    
    def _handle_trading_status(self, data):
        """Handle trading status updates"""
        status = data.get("status", "")
        enabled = data.get("enabled", False)
        
        # Update trading enabled flag
        self.trading_enabled = enabled
        
        self.logger.info(f"Trading status: {status}, enabled: {enabled}")
    
    def _handle_trading_error(self, data):
        """Handle trading errors"""
        error = data.get("error", "Unknown error")
        source = data.get("source", "unknown")
        
        self.logger.error(f"Trading error from {source}: {error}")
    
    def _update_components_for_event(self, event_type, data):
        """Update components that are interested in this event type"""
        for component_id, component_info in self.trading_components.items():
            component = component_info["component"]
            event_types = component_info["event_types"]
            
            if event_type in event_types:
                # Call specific update method if available
                if event_type == "trading.market_data" and hasattr(component, "update_market_data"):
                    component.update_market_data(data.get("data", {}))
                elif event_type == "trading.order_update" and hasattr(component, "update_orders"):
                    component.update_orders(data.get("orders", {}))
                elif event_type == "trading.portfolio_update" and hasattr(component, "update_portfolio"):
                    component.update_portfolio(data.get("portfolio", {}))
                elif event_type == "trading.status" and hasattr(component, "update_trading_status"):
                    component.update_trading_status(
                        data.get("status", ""),
                        data.get("enabled", False)
                    )
                # Fall back to generic update_from_event method
                elif hasattr(component, "update_from_event"):
                    component.update_from_event(event_type, data)
    
    def place_order(self, order_data):
        """
        Place a trading order
        
        Parameters:
        -----------
        order_data : dict
            Dictionary containing order details:
            - symbol: Trading symbol (e.g. 'BTC/USD')
            - side: 'buy' or 'sell'
            - type: 'market', 'limit', 'stop', etc.
            - amount: Amount to buy/sell
            - price: Price for limit orders
        """
        if not self.trading_enabled:
            self.logger.warning("Cannot place order: Trading is disabled")
            return False
        
        # Validate order data
        required_fields = ["symbol", "side", "type", "amount"]
        for field in required_fields:
            if field not in order_data:
                self.logger.error(f"Cannot place order: Missing required field '{field}'")
                return False
        
        # If it's a limit order, price is required
        if order_data.get("type") == "limit" and "price" not in order_data:
            self.logger.error("Cannot place limit order: Missing price")
            return False
        
        # Publish the order request
        if self.event_bus:
            self.event_bus.publish("trading.place_order", {
                "order": order_data
            })
            
            self.logger.info(f"Order request sent: {order_data['side']} {order_data['amount']} {order_data['symbol']}")
            return True
        else:
            self.logger.warning("Cannot place order: No event bus available")
            return False
    
    def cancel_order(self, order_id):
        """Cancel an existing order"""
        if not self.trading_enabled:
            self.logger.warning("Cannot cancel order: Trading is disabled")
            return False
        
        # Publish the cancel request
        if self.event_bus:
            self.event_bus.publish("trading.cancel_order", {
                "order_id": order_id
            })
            
            self.logger.info(f"Cancel order request sent for order {order_id}")
            return True
        else:
            self.logger.warning("Cannot cancel order: No event bus available")
            return False
    
    def request_market_data(self, symbols=None):
        """Request market data for specific symbols"""
        # Publish the request
        if self.event_bus:
            self.event_bus.publish("trading.request.market_data", {
                "symbols": symbols
            })
            
            if symbols:
                self.logger.info(f"Requested market data for symbols: {symbols}")
            else:
                self.logger.info("Requested market data for all symbols")
                
            return True
        else:
            self.logger.warning("Cannot request market data: No event bus available")
            return False
    
    def request_orders(self):
        """Request current orders"""
        # Publish the request
        if self.event_bus:
            self.event_bus.publish("trading.request.orders", {})
            
            self.logger.info("Requested current orders")
            return True
        else:
            self.logger.warning("Cannot request orders: No event bus available")
            return False
    
    def request_portfolio(self):
        """Request portfolio data"""
        # Publish the request
        if self.event_bus:
            self.event_bus.publish("trading.request.portfolio", {})
            
            self.logger.info("Requested portfolio data")
            return True
        else:
            self.logger.warning("Cannot request portfolio: No event bus available")
            return False

# Singleton instance for global access
_instance = None

def get_instance(event_bus=None, gui_binder=None):
    """Get the singleton instance of the trading binder"""
    global _instance
    if _instance is None:
        _instance = TradingBinder(event_bus, gui_binder)
    return _instance
