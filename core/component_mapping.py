#!/usr/bin/env python3
"""
Component Mapping System for Kingdom AI

This module provides a mapping between internal component names used in the component manager
and the display names shown in the loading screen and GUI. This ensures that all 32+ components
are properly displayed regardless of their internal implementation name.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger("KingdomAI.ComponentMapping")

# Map of internal component names to display names
# This allows the component manager to use different internal names
# while still showing the proper names in the UI
COMPONENT_NAME_MAP = {
    # Trading System Components
    "main_trading_system": "TradingSystem",
    "market_data_processor": "MarketDataStreaming",
    "order_executor": "OrderManagement",
    "risk_manager": "RiskManagement",
    "strategy_manager": "TradingStrategies",
    "trading_signal_generator": "CopyTrading",
    "position_manager": "WhaleTracker",
    "portfolio_manager": "PortfolioManager",
    
    # Blockchain Components
    "blockchain_config": "BlockchainManager",
    "blockchain_manager": "BlockchainManager",
    "bitcoin_connection": "WalletManager",
    "ethereum_connection": "SmartContracts",
    "transaction_verifier": "MemeCoins",
    "bitcoin_wallet": "MiningDashboard",
    
    # Security Components
    "security_manager": "SecurityManager",
    
    # Additional mappings for common components
    "thoth_connector": "ThothConnector",
    "redis_manager": "RedisManager",
    "api_key_manager": "APIKeyManager",
    "market_api": "MarketAPI",
    "config_manager": "ConfigManager",
    "vr_system": "VRSystem",
    "voice_system": "VoiceSystem",
    "error_resolution": "ErrorResolutionSystem",
    "continuous_response": "ContinuousResponseGenerator",
    "network_manager": "NetworkManager",
    "database_manager": "DatabaseManager",
    "meta_learning": "MetaLearning",
    "prediction_engine": "PredictionEngine",
    "intent_recognition": "IntentRecognition",
    "ai_contingency": "AIContingencySystem",
    "moonshot_integration": "MoonshotIntegration",
    "vr_ai_interface": "VR_AI_Interface"
}

# Reverse mapping (display name to internal name)
DISPLAY_TO_INTERNAL_MAP = {v: k for k, v in COMPONENT_NAME_MAP.items()}

# All expected component display names
ALL_COMPONENT_NAMES = [
    "ThothConnector", "RedisManager", "APIKeyManager", "BlockchainManager",
    "MarketAPI", "TradingSystem", "MiningSystem", "WalletManager",
    "SecurityManager", "ConfigManager", "VRSystem", "VoiceSystem",
    "ErrorResolutionSystem", "ContinuousResponseGenerator", "NetworkManager",
    "DatabaseManager", "MetaLearning", "PredictionEngine",
    "IntentRecognition", "AIContingencySystem", "CopyTrading",
    "MoonshotIntegration", "SmartContracts", "TradingStrategies",
    "WhaleTracker", "MemeCoins", "OrderManagement", "RiskManagement",
    "PortfolioManager", "MarketDataStreaming", "MiningDashboard", "VR_AI_Interface"
]

class ComponentMapper:
    """
    Handles mapping between internal component names and display names.
    Also provides utilities for component registration and status updates.
    """
    
    def __init__(self, event_bus=None):
        """Initialize the component mapper with an event bus."""
        self.event_bus = event_bus
        self.components_status = {}  # Track the status of all components
        self.logger = logging.getLogger("KingdomAI.ComponentMapper")
        self.logger.info("Component Mapper initialized")
    
    def set_event_bus(self, event_bus):
        """Set the event bus for the component mapper."""
        self.event_bus = event_bus
        self.logger.info("Event bus connected to Component Mapper")
    
    def get_display_name(self, internal_name: str) -> str:
        """Convert internal component name to display name."""
        return COMPONENT_NAME_MAP.get(internal_name.lower(), internal_name)
    
    def get_internal_name(self, display_name: str) -> str:
        """Convert display name to internal component name."""
        return DISPLAY_TO_INTERNAL_MAP.get(display_name, display_name.lower())
    
    async def register_all_components(self, component_manager=None):
        """
        Register all expected components with their current status.
        If component_manager is provided, uses it to check if components exist.
        """
        if not self.event_bus:
            self.logger.error("Cannot register components: No event bus connected")
            return False
        
        # Get actual components if component_manager is provided
        actual_components = []
        if component_manager and hasattr(component_manager, 'components'):
            if isinstance(component_manager.components, dict):
                actual_components = list(component_manager.components.keys())
            elif isinstance(component_manager.components, list):
                actual_components = component_manager.components
        
        # Register all expected components
        for display_name in ALL_COMPONENT_NAMES:
            internal_name = self.get_internal_name(display_name)
            exists = any(c.lower() == internal_name.lower() for c in actual_components) if actual_components else False
            
            # Additional check for alternative mappings
            if not exists:
                for actual_name in actual_components:
                    if self.get_display_name(actual_name) == display_name:
                        exists = True
                        break
            
            self.logger.debug(f"Registering component: {display_name} (internal: {internal_name}, exists: {exists})")
            
            # Publish component registration
            try:
                await self.event_bus.publish("component.registered", {
                    "name": display_name,
                    "status": "pending" if exists else "not_found",
                    "message": f"Preparing {display_name}..." if exists else f"Component {display_name} not found"
                })
                # Update internal status tracking
                self.components_status[display_name] = {
                    "status": "pending" if exists else "not_found",
                    "message": f"Preparing {display_name}..." if exists else f"Component {display_name} not found",
                    "exists": exists
                }
            except Exception as e:
                self.logger.error(f"Error registering component {display_name}: {e}")
        
        return True
    
    async def update_component_status(self, component_name: str, status: str, message: str):
        """
        Update the status of a component and publish it to the event bus.
        Uses internal name and converts to display name for the UI.
        """
        if not self.event_bus:
            self.logger.error("Cannot update component status: No event bus connected")
            return False
        
        display_name = self.get_display_name(component_name)
        
        try:
            # Update internal tracking
            self.components_status[display_name] = {
                "status": status,
                "message": message,
                "exists": True  # If we're updating status, component exists
            }
            
            # Publish status update
            await self.event_bus.publish("component.status", {
                "name": display_name,
                "status": status,
                "message": message
            })
            
            self.logger.debug(f"Updated component status: {display_name} -> {status}: {message}")
            return True
        except Exception as e:
            self.logger.error(f"Error updating component status for {display_name}: {e}")
            return False
    
    def get_component_status(self, component_name: str) -> Dict[str, Any]:
        """Get the current status of a component by its name (internal or display)."""
        # Try as display name first
        status = self.components_status.get(component_name)
        if status:
            return status
        
        # Try as internal name
        display_name = self.get_display_name(component_name)
        return self.components_status.get(display_name, {
            "status": "unknown",
            "message": "Component status unknown",
            "exists": False
        })

# Create a singleton instance
component_mapper = ComponentMapper()
