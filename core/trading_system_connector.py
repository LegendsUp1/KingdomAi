#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Trading System Connector

Integrates all trading components into a unified system, connecting the
CompetitiveEdgeAnalyzer, QuantumTradingOptimizer, and FuturesTradingMaster
without disrupting existing connections.
"""

import logging
import traceback
from datetime import datetime

# Kingdom AI imports
from core.base_component import BaseComponent
from core.trading_intelligence import CompetitiveEdgeAnalyzer
from core.quantum_trading_optimizer import QuantumTradingOptimizer
from core.futures_trading_master import FuturesTradingMaster
from core.trading_hub import TradingHub


class TradingSystemConnector(BaseComponent):
    """
    Connector that integrates all trading components into a unified system.
    
    This component ensures seamless communication between:
    1. CompetitiveEdgeAnalyzer - Core trading intelligence
    2. QuantumTradingOptimizer - Quantum-enhanced optimization
    3. FuturesTradingMaster - Advanced futures trading strategies
    4. TradingHub - Central coordination hub
    
    The connector preserves all existing connections and data flows while
    enhancing the system with new capabilities.
    """
    
    def __init__(self, event_bus=None, config=None):
        """
        Initialize the trading system connector.
        
        Args:
            event_bus: The event bus for publishing and subscribing to events
            config: Configuration parameters
        """
        super().__init__("TradingSystemConnector", event_bus, config)
        self.event_bus = event_bus
        self.config = config or {}
        self.logger = logging.getLogger('KingdomAI.TradingSystemConnector')
        
        # Component references
        self.trading_intelligence = None
        self.quantum_optimizer = None
        self.futures_trading_master = None
        self.trading_hub = None
        
        # Connection status
        self.connection_status = {
            'trading_intelligence': False,
            'quantum_optimizer': False,
            'futures_trading_master': False,
            'trading_hub': False
        }
        
        # Initialize the connector
        self._initialize_connector()
        
    def _initialize_connector(self):
        """Initialize the trading system connector."""
        self.logger.info("Initializing trading system connector")
        
        # Set up event subscriptions
        if self.event_bus:
            self.event_bus.subscribe('system.components.connected', self._handle_component_connection)
            self.event_bus.subscribe('system.components.disconnected', self._handle_component_disconnection)
        
        # Discover existing components
        self._discover_existing_components()
        
        # Connect components if needed
        self._connect_components()
        
        self.logger.info("Trading system connector initialized")
        
    def _discover_existing_components(self):
        """Discover existing trading components in the system."""
        self.logger.info("Discovering existing trading components")
        
        try:
            # Look for existing components in event bus subscribers
            if self.event_bus:
                subscribers = self.event_bus.get_subscribers('market.data')
                
                for component in subscribers:
                    if isinstance(component, CompetitiveEdgeAnalyzer):
                        self.trading_intelligence = component
                        self.connection_status['trading_intelligence'] = True
                        self.logger.info("Discovered existing CompetitiveEdgeAnalyzer")
                    elif isinstance(component, QuantumTradingOptimizer):
                        self.quantum_optimizer = component
                        self.connection_status['quantum_optimizer'] = True
                        self.logger.info("Discovered existing QuantumTradingOptimizer")
                    elif isinstance(component, FuturesTradingMaster):
                        self.futures_trading_master = component
                        self.connection_status['futures_trading_master'] = True
                        self.logger.info("Discovered existing FuturesTradingMaster")
                    elif isinstance(component, TradingHub):
                        self.trading_hub = component
                        self.connection_status['trading_hub'] = True
                        self.logger.info("Discovered existing TradingHub")
        
        except Exception as e:
            self.logger.error(f"Error discovering existing components: {e}")
            self.logger.error(traceback.format_exc())
            
    def _connect_components(self):
        """Connect trading components if they exist but aren't connected."""
        self.logger.info("Connecting trading components")
        
        try:
            # Create components that don't exist
            if not self.trading_intelligence:
                self.logger.info("Creating new CompetitiveEdgeAnalyzer")
                self.trading_intelligence = CompetitiveEdgeAnalyzer(self.event_bus, self.config.get('trading_intelligence', {}))
                self.connection_status['trading_intelligence'] = True
            
            # Create FuturesTradingMaster if it doesn't exist
            if not self.futures_trading_master:
                self.logger.info("Creating new FuturesTradingMaster")
                self.futures_trading_master = FuturesTradingMaster(self.event_bus, self.config.get('futures_trading_master', {}))
                self.connection_status['futures_trading_master'] = True
            
            # Connect FuturesTradingMaster to TradingIntelligence
            if self.futures_trading_master and self.trading_intelligence:
                self.futures_trading_master.connect_to_trading_intelligence(self.trading_intelligence)
                self.logger.info("Connected FuturesTradingMaster to CompetitiveEdgeAnalyzer")
            
            # Connect to TradingHub if it exists
            if self.trading_hub:
                if hasattr(self.trading_hub, 'register_component'):
                    self.trading_hub.register_component('futures_trading_master', self.futures_trading_master)
                    self.logger.info("Registered FuturesTradingMaster with TradingHub")
            
            # Publish connection status
            if self.event_bus:
                self.event_bus.publish('system.connector.status', {
                    'component': 'TradingSystemConnector',
                    'connections': self.connection_status,
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error connecting components: {e}")
            self.logger.error(traceback.format_exc())
    
    def _handle_component_connection(self, event_data):
        """
        Handle component connection events.
        
        Args:
            event_data: Component connection event data
        """
        try:
            source = event_data.get('source')
            target = event_data.get('target')
            
            self.logger.info(f"Component connection event: {source} -> {target}")
            
            # Update connection status
            if source == 'FuturesTradingMaster':
                self.connection_status['futures_trading_master'] = True
            elif source == 'CompetitiveEdgeAnalyzer':
                self.connection_status['trading_intelligence'] = True
            elif source == 'QuantumTradingOptimizer':
                self.connection_status['quantum_optimizer'] = True
            elif source == 'TradingHub':
                self.connection_status['trading_hub'] = True
                
        except Exception as e:
            self.logger.error(f"Error handling component connection: {e}")
    
    def _handle_component_disconnection(self, event_data):
        """
        Handle component disconnection events.
        
        Args:
            event_data: Component disconnection event data
        """
        try:
            component = event_data.get('component')
            
            self.logger.info(f"Component disconnection event: {component}")
            
            # Update connection status
            if component == 'FuturesTradingMaster':
                self.connection_status['futures_trading_master'] = False
            elif component == 'CompetitiveEdgeAnalyzer':
                self.connection_status['trading_intelligence'] = False
            elif component == 'QuantumTradingOptimizer':
                self.connection_status['quantum_optimizer'] = False
            elif component == 'TradingHub':
                self.connection_status['trading_hub'] = False
                
            # Attempt to reconnect
            self._reconnect_component(component)
                
        except Exception as e:
            self.logger.error(f"Error handling component disconnection: {e}")
    
    def _reconnect_component(self, component):
        """
        Attempt to reconnect a disconnected component.
        
        Args:
            component: Component to reconnect
        """
        try:
            self.logger.info(f"Attempting to reconnect {component}")
            
            # Implement reconnection logic based on component type
            if component == 'FuturesTradingMaster' and self.futures_trading_master:
                if self.trading_intelligence:
                    self.futures_trading_master.connect_to_trading_intelligence(self.trading_intelligence)
                    self.logger.info("Reconnected FuturesTradingMaster to CompetitiveEdgeAnalyzer")
                    
        except Exception as e:
            self.logger.error(f"Error reconnecting component {component}: {e}")
    
    def integrate_futures_trading(self):
        """
        Integrate futures trading capabilities with the existing trading system.
        
        This method ensures that the FuturesTradingMaster is properly connected
        to all other trading components and ready to provide advanced futures
        trading strategies.
        
        Returns:
            Boolean indicating successful integration
        """
        self.logger.info("Integrating futures trading capabilities")
        
        try:
            # Ensure FuturesTradingMaster exists
            if not self.futures_trading_master:
                self.logger.info("Creating new FuturesTradingMaster")
                self.futures_trading_master = FuturesTradingMaster(self.event_bus, self.config.get('futures_trading_master', {}))
            
            # Connect to TradingIntelligence
            if self.trading_intelligence:
                self.futures_trading_master.connect_to_trading_intelligence(self.trading_intelligence)
                self.logger.info("Connected FuturesTradingMaster to CompetitiveEdgeAnalyzer")
            
            # Register with TradingHub
            if self.trading_hub and hasattr(self.trading_hub, 'register_component'):
                self.trading_hub.register_component('futures_trading_master', self.futures_trading_master)
                self.logger.info("Registered FuturesTradingMaster with TradingHub")
            
            # Enable all futures trading strategies
            if hasattr(self.futures_trading_master, 'get_futures_trading_strategies'):
                strategies = self.futures_trading_master.get_futures_trading_strategies()
                self.logger.info(f"Enabled {len(strategies)} futures trading strategies")
            
            # Publish integration event
            if self.event_bus:
                self.event_bus.publish('system.integration.complete', {
                    'component': 'FuturesTradingMaster',
                    'strategies': list(strategies.keys()) if 'strategies' in locals() else [],
                    'timestamp': datetime.now().isoformat()
                })
                
            self.logger.info("Futures trading capabilities successfully integrated")
            return True
            
        except Exception as e:
            self.logger.error(f"Error integrating futures trading capabilities: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def get_component_status(self):
        """
        Get the status of all trading components.
        
        Returns:
            Dictionary with component status
        """
        return {
            'connection_status': self.connection_status,
            'components': {
                'trading_intelligence': bool(self.trading_intelligence),
                'quantum_optimizer': bool(self.quantum_optimizer),
                'futures_trading_master': bool(self.futures_trading_master),
                'trading_hub': bool(self.trading_hub)
            },
            'timestamp': datetime.now().isoformat()
        }
