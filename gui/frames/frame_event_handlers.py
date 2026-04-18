#!/usr/bin/env python3
"""
Frame Event Handlers for Kingdom AI GUI.
Implements event handling and component integration for all tab frames.
"""

import logging
import asyncio
from typing import Dict, Any, Callable, List

logger = logging.getLogger(__name__)

async def integrate_trading_frame(frame):
    """
    Integrate the TradingFrame with real-time data handlers.
    
    Args:
        frame: The TradingFrame instance
    """
    if not hasattr(frame, "set_trading_system"):
        # Add set_trading_system method
        def set_trading_system(self, trading_system):
            """Set the trading system component.
            
            This method connects the trading system component to this frame,
            enabling real-time data updates and trading functionality.
            
            Args:
                trading_system: The trading system component instance
            """
            logger.info("Setting trading system")
            self.trading_system = trading_system
            
            # Initialize the frame with data from the trading system
            if hasattr(trading_system, "get_available_symbols") and callable(trading_system.get_available_symbols):
                symbols = trading_system.get_available_symbols()
                if symbols and hasattr(self, "_handle_market_symbols"):
                    self._handle_market_symbols({"symbols": symbols})
            
            # Request initial data
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("trading.request.symbols", {}))
                asyncio.create_task(self.event_bus.publish("trading.request.portfolio", {}))
                
            logger.info("Trading system connected")
        
        frame.set_trading_system = set_trading_system.__get__(frame, type(frame))
    
    # Add event subscriptions if not already present
    if hasattr(frame, "event_bus") and frame.event_bus:
        asyncio.create_task(frame.event_bus.subscribe("market.update", frame._handle_market_update if hasattr(frame, "_handle_market_update") else default_market_update_handler(frame)))
        asyncio.create_task(frame.event_bus.subscribe("trading.update", frame._handle_trading_update if hasattr(frame, "_handle_trading_update") else default_trading_update_handler(frame)))
        asyncio.create_task(frame.event_bus.subscribe("market.orderbook.update", frame._handle_orderbook_update if hasattr(frame, "_handle_orderbook_update") else default_orderbook_update_handler(frame)))
        
    logger.info("Trading frame integrated with real-time data handlers")

async def integrate_mining_frame(frame):
    """
    Integrate the MiningFrame with real-time data handlers.
    
    Args:
        frame: The MiningFrame instance
    """
    if not hasattr(frame, "set_mining_system"):
        # Add set_mining_system method
        def set_mining_system(self, mining_system):
            """Set the mining system component.
            
            This method connects the mining system component to this frame,
            enabling real-time data updates and mining operations.
            
            Args:
                mining_system: The mining system component instance
            """
            logger.info("Setting mining system")
            self.mining_system = mining_system
            
            # Initialize with data from mining system
            if hasattr(mining_system, "get_mining_devices") and callable(mining_system.get_mining_devices):
                devices = mining_system.get_mining_devices()
                if devices and hasattr(self, "handle_devices_update"):
                    self.handle_devices_update({"devices": devices})
            
            # Request initial data
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("mining.request.status", {}))
                asyncio.create_task(self.event_bus.publish("mining.request.devices", {}))
            
            logger.info("Mining system connected")
        
        frame.set_mining_system = set_mining_system.__get__(frame, type(frame))
    
    # Add event subscriptions if not already present
    if hasattr(frame, "event_bus") and frame.event_bus:
        asyncio.create_task(frame.event_bus.subscribe("mining.status", frame.handle_mining_status if hasattr(frame, "handle_mining_status") else default_mining_status_handler(frame)))
        asyncio.create_task(frame.event_bus.subscribe("mining.update", frame.handle_hashrate_update if hasattr(frame, "handle_hashrate_update") else default_mining_update_handler(frame)))
        asyncio.create_task(frame.event_bus.subscribe("mining.rewards.update", frame.handle_rewards_update if hasattr(frame, "handle_rewards_update") else default_mining_rewards_handler(frame)))
        
    logger.info("Mining frame integrated with real-time data handlers")

async def integrate_wallet_frame(frame):
    """
    Integrate the WalletFrame with real-time data handlers.
    
    Args:
        frame: The WalletFrame instance
    """
    if not hasattr(frame, "set_wallet_manager"):
        # Add set_wallet_manager method
        def set_wallet_manager(self, wallet_manager):
            """Set the wallet manager component.
            
            This method connects the wallet manager component to this frame,
            enabling real-time balance and transaction updates.
            
            Args:
                wallet_manager: The wallet manager component instance
            """
            logger.info("Setting wallet manager")
            self.wallet_manager = wallet_manager
            
            # Request initial data
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("wallet.request.balances", {}))
                asyncio.create_task(self.event_bus.publish("wallet.request.transactions", {}))
            
            logger.info("Wallet manager connected")
        
        frame.set_wallet_manager = set_wallet_manager.__get__(frame, type(frame))
    
    # Add event subscriptions if not already present
    if hasattr(frame, "event_bus") and frame.event_bus:
        asyncio.create_task(frame.event_bus.subscribe("wallet.update", frame.handle_wallet_update if hasattr(frame, "handle_wallet_update") else default_wallet_update_handler(frame)))
        asyncio.create_task(frame.event_bus.subscribe("wallet.transaction", frame.handle_transaction_update if hasattr(frame, "handle_transaction_update") else default_transaction_update_handler(frame)))
        
    logger.info("Wallet frame integrated with real-time data handlers")

async def integrate_vr_frame(frame):
    """
    Integrate the VRFrame with real-time data handlers.
    
    Args:
        frame: The VRFrame instance
    """
    if not hasattr(frame, "set_vr_system"):
        # Add set_vr_system method
        def set_vr_system(self, vr_system):
            """Set the VR system component.
            
            This method connects the VR system component to this frame,
            enabling real-time VR environment updates.
            
            Args:
                vr_system: The VR system component instance
            """
            logger.info("Setting VR system")
            self.vr_system = vr_system
            
            # Request initial data
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("vr.request.status", {}))
                asyncio.create_task(self.event_bus.publish("vr.request.environment", {}))
            
            logger.info("VR system connected")
        
        frame.set_vr_system = set_vr_system.__get__(frame, type(frame))
    
    # Add event subscriptions if not already present
    if hasattr(frame, "event_bus") and frame.event_bus:
        asyncio.create_task(frame.event_bus.subscribe("vr.status", frame.handle_vr_status if hasattr(frame, "handle_vr_status") else default_vr_status_handler(frame)))
        asyncio.create_task(frame.event_bus.subscribe("vr.update", frame.handle_vr_update if hasattr(frame, "handle_vr_update") else default_vr_update_handler(frame)))
        
    logger.info("VR frame integrated with real-time data handlers")

async def integrate_thoth_frame(frame):
    """
    Integrate the ThothFrame with real-time data handlers.
    
    Args:
        frame: The ThothFrame instance
    """
    if not hasattr(frame, "set_thoth_ai"):
        # Add set_thoth_ai method
        def set_thoth_ai(self, thoth_ai):
            """Set the ThothAI component.
            
            This method connects the ThothAI component to this frame,
            enabling real-time AI responses and analysis.
            
            Args:
                thoth_ai: The ThothAI component instance
            """
            logger.info("Setting ThothAI")
            self.thoth_ai = thoth_ai
            
            # Request initial data
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("ai.request.status", {}))
                asyncio.create_task(self.event_bus.publish("system.metrics.request", {}))
            
            logger.info("ThothAI connected")
        
        frame.set_thoth_ai = set_thoth_ai.__get__(frame, type(frame))
    
    # Add event subscriptions if not already present
    if hasattr(frame, "event_bus") and frame.event_bus:
        asyncio.create_task(frame.event_bus.subscribe("ai.response", frame.handle_ai_response if hasattr(frame, "handle_ai_response") else default_ai_response_handler(frame)))
        asyncio.create_task(frame.event_bus.subscribe("system.metrics.analyze", frame.handle_metrics_analysis if hasattr(frame, "handle_metrics_analysis") else default_metrics_analysis_handler(frame)))
        
    logger.info("Thoth frame integrated with real-time data handlers")

async def integrate_code_generator_frame(frame):
    """
    Integrate the CodeGeneratorFrame with real-time data handlers.
    
    Args:
        frame: The CodeGeneratorFrame instance
    """
    if not hasattr(frame, "set_code_generator"):
        # Add set_code_generator method
        def set_code_generator(self, code_generator):
            """Set the Code Generator component.
            
            This method connects the Code Generator component to this frame,
            enabling real-time code generation.
            
            Args:
                code_generator: The Code Generator component instance
            """
            logger.info("Setting Code Generator")
            self.code_generator = code_generator
            
            # Request initial data
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("code.request.templates", {}))
                
            logger.info("Code Generator connected")
        
        frame.set_code_generator = set_code_generator.__get__(frame, type(frame))
    
    # Add event subscriptions if not already present
    if hasattr(frame, "event_bus") and frame.event_bus:
        asyncio.create_task(frame.event_bus.subscribe("code.generation.result", frame.handle_code_result if hasattr(frame, "handle_code_result") else default_code_result_handler(frame)))
        asyncio.create_task(frame.event_bus.subscribe("code.templates.update", frame.handle_templates_update if hasattr(frame, "handle_templates_update") else default_templates_update_handler(frame)))
        
    logger.info("Code Generator frame integrated with real-time data handlers")

async def integrate_api_keys_frame(frame):
    """
    Integrate the APIKeysFrame with real-time data handlers.
    
    Args:
        frame: The APIKeysFrame instance
    """
    if not hasattr(frame, "set_api_key_manager"):
        # Add set_api_key_manager method
        def set_api_key_manager(self, api_key_manager):
            """Set the API Key Manager component.
            
            This method connects the API Key Manager component to this frame,
            enabling real-time API key management.
            
            Args:
                api_key_manager: The API Key Manager component instance
            """
            logger.info("Setting API Key Manager")
            self.api_key_manager = api_key_manager
            
            # Request initial data
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("api.request.keys", {}))
                
            logger.info("API Key Manager connected")
        
        frame.set_api_key_manager = set_api_key_manager.__get__(frame, type(frame))
    
    # Add event subscriptions if not already present
    if hasattr(frame, "event_bus") and frame.event_bus:
        asyncio.create_task(frame.event_bus.subscribe("api.keys.update", frame.handle_keys_update if hasattr(frame, "handle_keys_update") else default_keys_update_handler(frame)))
        
    logger.info("API Keys frame integrated with real-time data handlers")

# Default handlers for each event type
def default_market_update_handler(frame):
    """Create a default market update handler for a frame."""
    async def handle_market_update(event_data):
        logger.info(f"Market update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_market_display(frame, event_data, type='market'))
    return handle_market_update

def default_trading_update_handler(frame):
    """Create a default trading update handler for a frame."""
    async def handle_trading_update(event_data):
        logger.info(f"Trading update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_trading_display(frame, event_data, type='trading'))
    return handle_trading_update

def default_orderbook_update_handler(frame):
    """Create a default order book update handler for a frame."""
    async def handle_orderbook_update(event_data):
        logger.info(f"Order book update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_orderbook_display(frame, event_data, type='orderbook'))
    return handle_orderbook_update

def default_mining_status_handler(frame):
    """Create a default mining status handler for a frame."""
    async def handle_mining_status(event_data):
        logger.info(f"Mining status update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_mining_status_display(frame, event_data, type='mining_status'))
    return handle_mining_status

def default_mining_update_handler(frame):
    """Create a default mining update handler for a frame."""
    async def handle_mining_update(event_data):
        logger.info(f"Mining update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_mining_display(frame, event_data, type='mining'))
    return handle_mining_update

def default_mining_rewards_handler(frame):
    """Create a default mining rewards handler for a frame."""
    async def handle_mining_rewards(event_data):
        logger.info(f"Mining rewards update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_mining_rewards_display(frame, event_data, type='mining_rewards'))
    return handle_mining_rewards

def default_wallet_update_handler(frame):
    """Create a default wallet update handler for a frame."""
    async def handle_wallet_update(event_data):
        logger.info(f"Wallet update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_wallet_display(frame, event_data, type='wallet'))
    return handle_wallet_update

def default_transaction_update_handler(frame):
    """Create a default transaction update handler for a frame."""
    async def handle_transaction_update(event_data):
        logger.info(f"Transaction update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_transaction_display(frame, event_data, type='transaction'))
    return handle_transaction_update

def default_vr_status_handler(frame):
    """Create a default VR status handler for a frame."""
    async def handle_vr_status(event_data):
        logger.info(f"VR status update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_vr_status_display(frame, event_data, type='vr_status'))
    return handle_vr_status

def default_vr_update_handler(frame):
    """Create a default VR update handler for a frame."""
    async def handle_vr_update(event_data):
        logger.info(f"VR update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_vr_display(frame, event_data, type='vr'))
    return handle_vr_update

def default_ai_response_handler(frame):
    """Create a default AI response handler for a frame."""
    async def handle_ai_response(event_data):
        logger.info(f"AI response received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_ai_response_display(frame, event_data, type='ai_response'))
    return handle_ai_response

def default_metrics_analysis_handler(frame):
    """Create a default metrics analysis handler for a frame."""
    async def handle_metrics_analysis(event_data):
        logger.info(f"Metrics analysis received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_metrics_display(frame, event_data, type='metrics'))
    return handle_metrics_analysis

def default_code_result_handler(frame):
    """Create a default code result handler for a frame."""
    async def handle_code_result(event_data):
        logger.info(f"Code result received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_code_result_display(frame, event_data, type='code_result'))
    return handle_code_result

def default_templates_update_handler(frame):
    """Create a default templates update handler for a frame."""
    async def handle_templates_update(event_data):
        logger.info(f"Templates update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_templates_display(frame, event_data, type='templates'))
    return handle_templates_update

def default_keys_update_handler(frame):
    """Create a default keys update handler for a frame."""
    async def handle_keys_update(event_data):
        logger.info(f"Keys update received: {event_data}")
        if hasattr(frame, "after"):
            frame.after(0, lambda: update_keys_display(frame, event_data, type='keys'))
    return handle_keys_update

# Helper functions for updating display
def update_market_display(frame, event_data, type='market'):
    logger.info(f"Updating market display with data: {event_data}")
    if hasattr(frame, 'market_label'):
        frame.market_label.config(text=f"Market Data: {event_data.get('price', 'N/A')}")
    return None

def update_trading_display(frame, event_data, type='trading'):
    logger.info(f"Updating trading display with data: {event_data}")
    if hasattr(frame, 'trading_label'):
        frame.trading_label.config(text=f"Trading Data: {event_data.get('status', 'N/A')}")
    return None

def update_orderbook_display(frame, event_data, type='orderbook'):
    logger.info(f"Updating orderbook display with data: {event_data}")
    if hasattr(frame, 'orderbook_label'):
        frame.orderbook_label.config(text=f"Orderbook: {event_data.get('bids', 'N/A')}")
    return None

def update_mining_status_display(frame, event_data, type='mining_status'):
    logger.info(f"Updating mining status display with data: {event_data}")
    if hasattr(frame, 'mining_status_label'):
        frame.mining_status_label.config(text=f"Mining Status: {event_data.get('status', 'N/A')}")
    return None

def update_mining_display(frame, event_data, type='mining'):
    logger.info(f"Updating mining display with data: {event_data}")
    if hasattr(frame, 'mining_label'):
        frame.mining_label.config(text=f"Mining Data: {event_data.get('hashrate', 'N/A')}")
    return None

def update_mining_rewards_display(frame, event_data, type='mining_rewards'):
    logger.info(f"Updating mining rewards display with data: {event_data}")
    if hasattr(frame, 'mining_rewards_label'):
        frame.mining_rewards_label.config(text=f"Mining Rewards: {event_data.get('amount', 'N/A')}")
    return None

def update_wallet_display(frame, event_data, type='wallet'):
    logger.info(f"Updating wallet display with data: {event_data}")
    if hasattr(frame, 'wallet_label'):
        frame.wallet_label.config(text=f"Wallet Balance: {event_data.get('balance', 'N/A')}")
    return None

def update_transaction_display(frame, event_data, type='transaction'):
    logger.info(f"Updating transaction display with data: {event_data}")
    if hasattr(frame, 'transaction_label'):
        frame.transaction_label.config(text=f"Transaction: {event_data.get('txid', 'N/A')}")
    return None

def update_vr_status_display(frame, event_data, type='vr_status'):
    logger.info(f"Updating VR status display with data: {event_data}")
    if hasattr(frame, 'vr_status_label'):
        frame.vr_status_label.config(text=f"VR Status: {event_data.get('status', 'N/A')}")
    return None

def update_vr_display(frame, event_data, type='vr'):
    logger.info(f"Updating VR display with data: {event_data}")
    if hasattr(frame, 'vr_label'):
        frame.vr_label.config(text=f"VR Data: {event_data.get('data', 'N/A')}")
    return None

def update_ai_response_display(frame, event_data, type='ai_response'):
    logger.info(f"Updating AI response display with data: {event_data}")
    if hasattr(frame, 'ai_response_label'):
        frame.ai_response_label.config(text=f"AI Response: {event_data.get('response', 'N/A')}")
    return None

def update_metrics_display(frame, event_data, type='metrics'):
    logger.info(f"Updating metrics display with data: {event_data}")
    if hasattr(frame, 'metrics_label'):
        frame.metrics_label.config(text=f"Metrics: {event_data.get('analysis', 'N/A')}")
    return None

def update_code_result_display(frame, event_data, type='code_result'):
    logger.info(f"Updating code result display with data: {event_data}")
    if hasattr(frame, 'code_result_label'):
        frame.code_result_label.config(text=f"Code Result: {event_data.get('code', 'N/A')}")
    return None

def update_templates_display(frame, event_data, type='templates'):
    logger.info(f"Updating templates display with data: {event_data}")
    if hasattr(frame, 'templates_label'):
        frame.templates_label.config(text=f"Templates: {event_data.get('templates', 'N/A')}")
    return None

def update_keys_display(frame, event_data, type='keys'):
    logger.info(f"Updating keys display with data: {event_data}")
    if hasattr(frame, 'keys_label'):
        frame.keys_label.config(text=f"API Keys: {event_data.get('keys', 'N/A')}")
    return None

class FrameEventManager:
    def __init__(self, event_bus=None, logger=None):
        self.event_bus = event_bus if event_bus else None
        self.logger = logger if logger else logging.getLogger(__name__)
        self.trading_frame = None
        self.mining_frame = None
        self.wallet_frame = None
        self.vr_frame = None
        self.thoth_frame = None
        self.code_generator_frame = None
        self.api_keys_frame = None

    def set_trading_frame(self, frame):
        self.trading_frame = frame

    def set_mining_frame(self, frame):
        self.mining_frame = frame

    def set_wallet_frame(self, frame):
        self.wallet_frame = frame

    def set_vr_frame(self, frame):
        self.vr_frame = frame

    def set_thoth_frame(self, frame):
        self.thoth_frame = frame

    def set_code_generator_frame(self, frame):
        self.code_generator_frame = frame

    def set_api_keys_frame(self, frame):
        self.api_keys_frame = frame

    async def integrate_trading_frame(self, frame):
        """Integrate a trading frame with real-time data handlers."""
        if not hasattr(frame, 'event_bus') or not frame.event_bus:
            if self.logger:
                self.logger.warning("No event bus available for trading frame integration")
            return
        
        # Add event subscriptions if not already present
        if hasattr(frame, "event_bus") and frame.event_bus:
            asyncio.create_task(frame.event_bus.subscribe("market.update", frame._handle_market_update if hasattr(frame, "_handle_market_update") else default_market_update_handler(frame)))
            asyncio.create_task(frame.event_bus.subscribe("trading.update", frame._handle_trading_update if hasattr(frame, "_handle_trading_update") else default_trading_update_handler(frame)))
            asyncio.create_task(frame.event_bus.subscribe("market.orderbook.update", frame._handle_orderbook_update if hasattr(frame, "_handle_orderbook_update") else default_orderbook_update_handler(frame)))
        
        if self.logger:
            self.logger.info("Trading frame integrated with real-time data handlers")

    async def integrate_mining_frame(self, frame):
        """Integrate a mining frame with real-time data handlers."""
        if not hasattr(frame, 'event_bus') or not frame.event_bus:
            if self.logger:
                self.logger.warning("No event bus available for mining frame integration")
            return
        
        # Add event subscriptions if not already present
        if hasattr(frame, "event_bus") and frame.event_bus:
            asyncio.create_task(frame.event_bus.subscribe("mining.status", frame.handle_mining_status if hasattr(frame, "handle_mining_status") else default_mining_status_handler(frame)))
            asyncio.create_task(frame.event_bus.subscribe("mining.update", frame.handle_hashrate_update if hasattr(frame, "handle_hashrate_update") else default_mining_update_handler(frame)))
            asyncio.create_task(frame.event_bus.subscribe("mining.rewards.update", frame.handle_rewards_update if hasattr(frame, "handle_rewards_update") else default_mining_rewards_handler(frame)))
        
        if self.logger:
            self.logger.info("Mining frame integrated with real-time data handlers")

    async def integrate_wallet_frame(self, frame):
        """Integrate a wallet frame with real-time data handlers."""
        if not hasattr(frame, 'event_bus') or not frame.event_bus:
            if self.logger:
                self.logger.warning("No event bus available for wallet frame integration")
            return
        
        # Add event subscriptions if not already present
        if hasattr(frame, "event_bus") and frame.event_bus:
            asyncio.create_task(frame.event_bus.subscribe("wallet.update", frame.handle_wallet_update if hasattr(frame, "handle_wallet_update") else default_wallet_update_handler(frame)))
            asyncio.create_task(frame.event_bus.subscribe("wallet.transaction", frame.handle_transaction_update if hasattr(frame, "handle_transaction_update") else default_transaction_update_handler(frame)))
        
        if self.logger:
            self.logger.info("Wallet frame integrated with real-time data handlers")

    async def integrate_vr_frame(self, frame):
        """Integrate a VR frame with real-time data handlers."""
        if not hasattr(frame, 'event_bus') or not frame.event_bus:
            if self.logger:
                self.logger.warning("No event bus available for VR frame integration")
            return
        
        # Add event subscriptions if not already present
        if hasattr(frame, "event_bus") and frame.event_bus:
            asyncio.create_task(frame.event_bus.subscribe("vr.status", frame.handle_vr_status if hasattr(frame, "handle_vr_status") else default_vr_status_handler(frame)))
            asyncio.create_task(frame.event_bus.subscribe("vr.update", frame.handle_vr_update if hasattr(frame, "handle_vr_update") else default_vr_update_handler(frame)))
        
        if self.logger:
            self.logger.info("VR frame integrated with real-time data handlers")

    async def integrate_thoth_frame(self, frame):
        """Integrate a Thoth frame with real-time data handlers."""
        if not hasattr(frame, 'event_bus') or not frame.event_bus:
            if self.logger:
                self.logger.warning("No event bus available for Thoth frame integration")
            return
        
        # Add event subscriptions if not already present
        if hasattr(frame, "event_bus") and frame.event_bus:
            asyncio.create_task(frame.event_bus.subscribe("ai.response", frame.handle_ai_response if hasattr(frame, "handle_ai_response") else default_ai_response_handler(frame)))
            asyncio.create_task(frame.event_bus.subscribe("system.metrics.analyze", frame.handle_metrics_analysis if hasattr(frame, "handle_metrics_analysis") else default_metrics_analysis_handler(frame)))
        
        if self.logger:
            self.logger.info("Thoth frame integrated with real-time data handlers")

    async def integrate_code_generator_frame(self, frame):
        """Integrate a code generator frame with real-time data handlers."""
        if not hasattr(frame, 'event_bus') or not frame.event_bus:
            if self.logger:
                self.logger.warning("No event bus available for Code Generator frame integration")
            return
        
        # Add event subscriptions if not already present
        if hasattr(frame, "event_bus") and frame.event_bus:
            asyncio.create_task(frame.event_bus.subscribe("code.generation.result", frame.handle_code_result if hasattr(frame, "handle_code_result") else default_code_result_handler(frame)))
            asyncio.create_task(frame.event_bus.subscribe("code.templates.update", frame.handle_templates_update if hasattr(frame, "handle_templates_update") else default_templates_update_handler(frame)))
        
        if self.logger:
            self.logger.info("Code Generator frame integrated with real-time data handlers")

    async def integrate_api_keys_frame(self, frame):
        """Integrate an API keys frame with real-time data handlers."""
        if not hasattr(frame, 'event_bus') or not frame.event_bus:
            if self.logger:
                self.logger.warning("No event bus available for API Keys frame integration")
            return
        
        # Add event subscriptions if not already present
        if hasattr(frame, "event_bus") and frame.event_bus:
            asyncio.create_task(frame.event_bus.subscribe("api.keys.update", frame.handle_keys_update if hasattr(frame, "handle_keys_update") else default_keys_update_handler(frame)))
        
        if self.logger:
            self.logger.info("API Keys frame integrated with real-time data handlers")
    
    async def _request_initial_trading_data(self):
        """Request initial trading data."""
        try:
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("trading.request.symbols", {}))
                asyncio.create_task(self.event_bus.publish("trading.request.balance", {}))
                asyncio.create_task(self.event_bus.publish("trading.request.positions", {}))
                asyncio.create_task(self.event_bus.publish("trading.request.orders", {}))
                asyncio.create_task(self.event_bus.publish("trading.request.performance", {}))
                asyncio.create_task(self.event_bus.publish("trading.request.historical_data", {"symbol": "BTCUSDT", "timeframe": "1h", "limit": 100}))
                if self.logger:
                    self.logger.info("Requested initial trading data")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error requesting initial trading data: {e}")

    async def _setup_trading_callbacks(self):
        """Set up trading event callbacks."""
        try:
            if self.event_bus and self.trading_frame:
                asyncio.create_task(self.event_bus.subscribe("trading.symbols", self.trading_frame.update_symbols))
                asyncio.create_task(self.event_bus.subscribe("trading.balance", self.trading_frame.update_balance))
                asyncio.create_task(self.event_bus.subscribe("trading.positions", self.trading_frame.update_positions))
                asyncio.create_task(self.event_bus.subscribe("trading.orders", self.trading_frame.update_orders))
                asyncio.create_task(self.event_bus.subscribe("trading.performance", self.trading_frame.update_performance))
                asyncio.create_task(self.event_bus.subscribe("trading.historical_data", self.trading_frame.update_historical_data))
                asyncio.create_task(self.event_bus.subscribe("trading.order_executed", self.trading_frame.handle_order_executed))
                asyncio.create_task(self.event_bus.subscribe("trading.strategy_signal", self.trading_frame.handle_strategy_signal))
                asyncio.create_task(self.event_bus.subscribe("trading.risk_alert", self.trading_frame.handle_risk_alert))
                asyncio.create_task(self.event_bus.subscribe("trading.connection_status", self.trading_frame.handle_connection_status))
                if self.logger:
                    self.logger.info("Trading callbacks set up successfully")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error setting up trading callbacks: {e}")

    async def _request_initial_mining_data(self):
        """Request initial mining data."""
        try:
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("mining.request.stats", {}))
                asyncio.create_task(self.event_bus.publish("mining.request.pool_info", {}))
                asyncio.create_task(self.event_bus.publish("mining.request.worker_status", {}))
                asyncio.create_task(self.event_bus.publish("mining.request.hashrate_history", {"limit": 100}))
                asyncio.create_task(self.event_bus.publish("mining.request.earnings", {}))
                if self.logger:
                    self.logger.info("Requested initial mining data")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error requesting initial mining data: {e}")

    async def _setup_mining_callbacks(self):
        """Set up mining event callbacks."""
        try:
            if self.event_bus and self.mining_frame:
                asyncio.create_task(self.event_bus.subscribe("mining.stats", self.mining_frame.update_stats))
                asyncio.create_task(self.event_bus.subscribe("mining.pool_info", self.mining_frame.update_pool_info))
                asyncio.create_task(self.event_bus.subscribe("mining.worker_status", self.mining_frame.update_worker_status))
                asyncio.create_task(self.event_bus.subscribe("mining.hashrate_history", self.mining_frame.update_hashrate_history))
                asyncio.create_task(self.event_bus.subscribe("mining.earnings", self.mining_frame.update_earnings))
                asyncio.create_task(self.event_bus.subscribe("mining.alert", self.mining_frame.handle_alert))
                asyncio.create_task(self.event_bus.subscribe("mining.connection_status", self.mining_frame.handle_connection_status))
                if self.logger:
                    self.logger.info("Mining callbacks set up successfully")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error setting up mining callbacks: {e}")

    async def _request_initial_wallet_data(self):
        """Request initial wallet data."""
        try:
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("wallet.request.balances", {}))
                asyncio.create_task(self.event_bus.publish("wallet.request.transactions", {"limit": 50}))
                asyncio.create_task(self.event_bus.publish("wallet.request.addresses", {}))
                asyncio.create_task(self.event_bus.publish("wallet.request.networks", {}))
                if self.logger:
                    self.logger.info("Requested initial wallet data")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error requesting initial wallet data: {e}")

    async def _setup_wallet_callbacks(self):
        """Set up wallet event callbacks."""
        try:
            if self.event_bus and self.wallet_frame:
                asyncio.create_task(self.event_bus.subscribe("wallet.balances", self.wallet_frame.update_balances))
                asyncio.create_task(self.event_bus.subscribe("wallet.transactions", self.wallet_frame.update_transactions))
                asyncio.create_task(self.event_bus.subscribe("wallet.addresses", self.wallet_frame.update_addresses))
                asyncio.create_task(self.event_bus.subscribe("wallet.networks", self.wallet_frame.update_networks))
                asyncio.create_task(self.event_bus.subscribe("wallet.transaction_status", self.wallet_frame.handle_transaction_status))
                asyncio.create_task(self.event_bus.subscribe("wallet.connection_status", self.wallet_frame.handle_connection_status))
                if self.logger:
                    self.logger.info("Wallet callbacks set up successfully")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error setting up wallet callbacks: {e}")

    async def _request_initial_vr_data(self):
        """Request initial VR data."""
        try:
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("vr.request.environment", {}))
                asyncio.create_task(self.event_bus.publish("vr.request.avatar", {}))
                asyncio.create_task(self.event_bus.publish("vr.request.interactables", {}))
                if self.logger:
                    self.logger.info("Requested initial VR data")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error requesting initial VR data: {e}")

    async def _setup_vr_callbacks(self):
        """Set up VR event callbacks."""
        try:
            if self.event_bus and self.vr_frame:
                asyncio.create_task(self.event_bus.subscribe("vr.environment", self.vr_frame.update_environment))
                asyncio.create_task(self.event_bus.subscribe("vr.avatar", self.vr_frame.update_avatar))
                asyncio.create_task(self.event_bus.subscribe("vr.interactables", self.vr_frame.update_interactables))
                asyncio.create_task(self.event_bus.subscribe("vr.interaction", self.vr_frame.handle_interaction))
                asyncio.create_task(self.event_bus.subscribe("vr.connection_status", self.vr_frame.handle_connection_status))
                if self.logger:
                    self.logger.info("VR callbacks set up successfully")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error setting up VR callbacks: {e}")

    async def _request_initial_thoth_data(self):
        """Request initial Thoth data."""
        try:
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("thoth.request.models", {}))
                asyncio.create_task(self.event_bus.publish("thoth.request.conversations", {"limit": 10}))
                asyncio.create_task(self.event_bus.publish("thoth.request.capabilities", {}))
                if self.logger:
                    self.logger.info("Requested initial Thoth data")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error requesting initial Thoth data: {e}")

    async def _setup_thoth_callbacks(self):
        """Set up Thoth event callbacks."""
        try:
            if self.event_bus and self.thoth_frame:
                asyncio.create_task(self.event_bus.subscribe("thoth.models", self.thoth_frame.update_models))
                asyncio.create_task(self.event_bus.subscribe("thoth.conversations", self.thoth_frame.update_conversations))
                asyncio.create_task(self.event_bus.subscribe("thoth.capabilities", self.thoth_frame.update_capabilities))
                asyncio.create_task(self.event_bus.subscribe("thoth.message", self.thoth_frame.handle_message))
                asyncio.create_task(self.event_bus.subscribe("thoth.connection_status", self.thoth_frame.handle_connection_status))
                if self.logger:
                    self.logger.info("Thoth callbacks set up successfully")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error setting up Thoth callbacks: {e}")

    async def _request_initial_code_generator_data(self):
        """Request initial code generator data."""
        try:
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("code_generator.request.templates", {}))
                asyncio.create_task(self.event_bus.publish("code_generator.request.projects", {"limit": 10}))
                asyncio.create_task(self.event_bus.publish("code_generator.request.languages", {}))
                if self.logger:
                    self.logger.info("Requested initial code generator data")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error requesting initial code generator data: {e}")

    async def _setup_code_generator_callbacks(self):
        """Set up code generator event callbacks."""
        try:
            if self.event_bus and self.code_generator_frame:
                asyncio.create_task(self.event_bus.subscribe("code_generator.templates", self.code_generator_frame.update_templates))
                asyncio.create_task(self.event_bus.subscribe("code_generator.projects", self.code_generator_frame.update_projects))
                asyncio.create_task(self.event_bus.subscribe("code_generator.languages", self.code_generator_frame.update_languages))
                asyncio.create_task(self.event_bus.subscribe("code_generator.code_generated", self.code_generator_frame.handle_code_generated))
                asyncio.create_task(self.event_bus.subscribe("code_generator.connection_status", self.code_generator_frame.handle_connection_status))
                if self.logger:
                    self.logger.info("Code generator callbacks set up successfully")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error setting up code generator callbacks: {e}")

    async def _request_initial_api_keys_data(self):
        """Request initial API keys data."""
        try:
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("api_keys.request.keys", {}))
                asyncio.create_task(self.event_bus.publish("api_keys.request.services", {}))
                if self.logger:
                    self.logger.info("Requested initial API keys data")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error requesting initial API keys data: {e}")

    async def _setup_api_keys_callbacks(self):
        """Set up API keys event callbacks."""
        try:
            if self.event_bus and self.api_keys_frame:
                asyncio.create_task(self.event_bus.subscribe("api_keys.keys", self.api_keys_frame.update_keys))
                asyncio.create_task(self.event_bus.subscribe("api_keys.services", self.api_keys_frame.update_services))
                asyncio.create_task(self.event_bus.subscribe("api_keys.key_updated", self.api_keys_frame.handle_key_updated))
                asyncio.create_task(self.event_bus.subscribe("api_keys.connection_status", self.api_keys_frame.handle_connection_status))
                if self.logger:
                    self.logger.info("API keys callbacks set up successfully")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error setting up API keys callbacks: {e}")

    async def initialize_frame_data(self, frame_name: str):
        """Initialize data for a specific frame."""
        try:
            if frame_name == "trading":
                await self._request_initial_trading_data()
            elif frame_name == "mining":
                await self._request_initial_mining_data()
            elif frame_name == "wallet":
                await self._request_initial_wallet_data()
            elif frame_name == "vr":
                await self._request_initial_vr_data()
            elif frame_name == "thoth":
                await self._request_initial_thoth_data()
            elif frame_name == "code_generator":
                await self._request_initial_code_generator_data()
            elif frame_name == "api_keys":
                await self._request_initial_api_keys_data()
            else:
                if self.logger:
                    self.logger.warning(f"Unknown frame name for initialization: {frame_name}")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error initializing frame data for {frame_name}: {e}")

    async def setup_frame_callbacks(self, frame_name: str):
        """Set up callbacks for a specific frame."""
        try:
            if frame_name == "trading":
                await self._setup_trading_callbacks()
            elif frame_name == "mining":
                await self._setup_mining_callbacks()
            elif frame_name == "wallet":
                await self._setup_wallet_callbacks()
            elif frame_name == "vr":
                await self._setup_vr_callbacks()
            elif frame_name == "thoth":
                await self._setup_thoth_callbacks()
            elif frame_name == "code_generator":
                await self._setup_code_generator_callbacks()
            elif frame_name == "api_keys":
                await self._setup_api_keys_callbacks()
            else:
                if self.logger:
                    self.logger.warning(f"Unknown frame name for callback setup: {frame_name}")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error setting up frame callbacks for {frame_name}: {e}")

    async def initialize_all_frames(self):
        """Initialize all frames with initial data requests."""
        try:
            await self._request_initial_trading_data()
            await self._request_initial_mining_data()
            await self._request_initial_wallet_data()
            await self._request_initial_vr_data()
            await self._request_initial_thoth_data()
            await self._request_initial_code_generator_data()
            await self._request_initial_api_keys_data()
            if self.logger:
                self.logger.info("All frames initialized with initial data requests")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error initializing all frames: {e}")

    async def setup_all_callbacks(self):
        """Set up callbacks for all frames."""
        try:
            await self._setup_trading_callbacks()
            await self._setup_mining_callbacks()
            await self._setup_wallet_callbacks()
            await self._setup_vr_callbacks()
            await self._setup_thoth_callbacks()
            await self._setup_code_generator_callbacks()
            await self._setup_api_keys_callbacks()
            if self.logger:
                self.logger.info("All callbacks set up successfully")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error setting up all callbacks: {e}")

    async def setup_trading_frame_handlers(self, trading_frame):
        """Set up event handlers for the trading frame."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized in FrameEventManager")
            return
        
        if not hasattr(trading_frame, 'market_frame') or not hasattr(trading_frame, 'orderbook_frame') or not hasattr(trading_frame, 'trade_history_frame'):
            logger.error("Trading frame components not fully initialized")
            return
        
        logger.info("Setting up trading frame handlers")
        self.trading_frame = trading_frame
        # Market frame handlers
        market_frame = trading_frame.market_frame
        if hasattr(market_frame, 'handle_market_symbols'):
            asyncio.create_task(self.event_bus.subscribe("market_symbols", market_frame.handle_market_symbols))
        if hasattr(market_frame, 'handle_market_update'):
            asyncio.create_task(self.event_bus.subscribe("market_update", market_frame.handle_market_update))
        if hasattr(market_frame, 'handle_trading_update'):
            asyncio.create_task(self.event_bus.subscribe("trading_update", market_frame.handle_trading_update))
        if hasattr(market_frame, 'handle_orderbook_update'):
            asyncio.create_task(self.event_bus.subscribe("orderbook_update", market_frame.handle_orderbook_update))
        
        # Orderbook frame handlers
        orderbook_frame = trading_frame.orderbook_frame
        if hasattr(orderbook_frame, 'handle_orderbook_update'):
            asyncio.create_task(self.event_bus.subscribe("orderbook_update", orderbook_frame.handle_orderbook_update))
        
        # Trade history frame handlers
        trade_history_frame = trading_frame.trade_history_frame
        if hasattr(trade_history_frame, 'handle_trade_history'):
            asyncio.create_task(self.event_bus.subscribe("trade_history", trade_history_frame.handle_trade_history))
        
        logger.info("Trading frame handlers setup complete")
        await self._request_initial_trading_data()

    async def _request_initial_trading_data(self):
        """Request initial trading data from the event bus."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized for requesting trading data")
            return
        
        logger.info("Requesting initial trading data")
        try:
            asyncio.create_task(self.event_bus.publish("request_market_data", {"request": "initial_data"}))
            asyncio.create_task(self.event_bus.publish("request_trading_data", {"request": "initial_data"}))
            asyncio.create_task(self.event_bus.publish("request_orderbook_data", {"request": "initial_data"}))
            asyncio.create_task(self.event_bus.publish("request_trade_history", {"request": "initial_data"}))
            logger.info("Initial trading data requested")
        except Exception as e:
            logger.error(f"Error requesting initial trading data: {e}", exc_info=True)

    async def setup_mining_frame_handlers(self, mining_frame):
        """Set up event handlers for the mining frame."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized in FrameEventManager")
            return
        
        if not hasattr(mining_frame, 'mining_status_frame') or not hasattr(mining_frame, 'mining_rewards_frame'):
            logger.error("Mining frame components not fully initialized")
            return
        
        logger.info("Setting up mining frame handlers")
        self.mining_frame = mining_frame
        # Mining status frame handlers
        mining_status_frame = mining_frame.mining_status_frame
        if hasattr(mining_status_frame, 'handle_mining_status'):
            asyncio.create_task(self.event_bus.subscribe("mining_status", mining_status_frame.handle_mining_status))
        if hasattr(mining_status_frame, 'handle_mining_update'):
            asyncio.create_task(self.event_bus.subscribe("mining_update", mining_status_frame.handle_mining_update))
        
        # Mining rewards frame handlers
        mining_rewards_frame = mining_frame.mining_rewards_frame
        if hasattr(mining_rewards_frame, 'handle_mining_rewards'):
            asyncio.create_task(self.event_bus.subscribe("mining_rewards", mining_rewards_frame.handle_mining_rewards))
        
        logger.info("Mining frame handlers setup complete")
        await self._request_initial_mining_data()

    async def _request_initial_mining_data(self):
        """Request initial mining data from the event bus."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized for requesting mining data")
            return
        
        logger.info("Requesting initial mining data")
        try:
            asyncio.create_task(self.event_bus.publish("request_mining_data", {"request": "initial_data"}))
            asyncio.create_task(self.event_bus.publish("request_mining_rewards", {"request": "initial_data"}))
            logger.info("Initial mining data requested")
        except Exception as e:
            logger.error(f"Error requesting initial mining data: {e}", exc_info=True)

    async def setup_wallet_frame_handlers(self, wallet_frame):
        """Set up event handlers for the wallet frame."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized in FrameEventManager")
            return
        
        if not hasattr(wallet_frame, 'wallet_balance_frame') or not hasattr(wallet_frame, 'transaction_frame'):
            logger.error("Wallet frame components not fully initialized")
            return
        
        logger.info("Setting up wallet frame handlers")
        self.wallet_frame = wallet_frame
        # Wallet balance frame handlers
        wallet_balance_frame = wallet_frame.wallet_balance_frame
        if hasattr(wallet_balance_frame, 'handle_wallet_update'):
            asyncio.create_task(self.event_bus.subscribe("wallet_update", wallet_balance_frame.handle_wallet_update))
        
        # Transaction frame handlers
        transaction_frame = wallet_frame.transaction_frame
        if hasattr(transaction_frame, 'handle_transaction_update'):
            asyncio.create_task(self.event_bus.subscribe("transaction_update", transaction_frame.handle_transaction_update))
        
        logger.info("Wallet frame handlers setup complete")
        await self._request_initial_wallet_data()

    async def _request_initial_wallet_data(self):
        """Request initial wallet data from the event bus."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized for requesting wallet data")
            return
        
        logger.info("Requesting initial wallet data")
        try:
            asyncio.create_task(self.event_bus.publish("request_wallet_data", {"request": "initial_data"}))
            asyncio.create_task(self.event_bus.publish("request_transaction_data", {"request": "initial_data"}))
            logger.info("Initial wallet data requested")
        except Exception as e:
            logger.error(f"Error requesting initial wallet data: {e}", exc_info=True)

    async def setup_vr_frame_handlers(self, vr_frame):
        """Set up event handlers for the VR frame."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized in FrameEventManager")
            return
        
        if not hasattr(vr_frame, 'vr_status_frame'):
            logger.error("VR frame components not fully initialized")
            return
        
        logger.info("Setting up VR frame handlers")
        self.vr_frame = vr_frame
        # VR status frame handlers
        vr_status_frame = vr_frame.vr_status_frame
        if hasattr(vr_status_frame, 'handle_vr_status'):
            asyncio.create_task(self.event_bus.subscribe("vr_status", vr_status_frame.handle_vr_status))
        if hasattr(vr_status_frame, 'handle_vr_update'):
            asyncio.create_task(self.event_bus.subscribe("vr_update", vr_status_frame.handle_vr_update))
        
        logger.info("VR frame handlers setup complete")
        await self._request_initial_vr_data()

    async def _request_initial_vr_data(self):
        """Request initial VR data from the event bus."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized for requesting VR data")
            return
        
        logger.info("Requesting initial VR data")
        try:
            asyncio.create_task(self.event_bus.publish("request_vr_data", {"request": "initial_data"}))
            logger.info("Initial VR data requested")
        except Exception as e:
            logger.error(f"Error requesting initial VR data: {e}", exc_info=True)

    async def setup_ai_frame_handlers(self, ai_frame):
        """Set up event handlers for the AI frame."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized in FrameEventManager")
            return
        
        if not hasattr(ai_frame, 'ai_response_frame') or not hasattr(ai_frame, 'metrics_frame'):
            logger.error("AI frame components not fully initialized")
            return
        
        logger.info("Setting up AI frame handlers")
        self.ai_frame = ai_frame
        # AI response frame handlers
        ai_response_frame = ai_frame.ai_response_frame
        if hasattr(ai_response_frame, 'handle_ai_response'):
            asyncio.create_task(self.event_bus.subscribe("ai_response", ai_response_frame.handle_ai_response))
        
        # Metrics frame handlers
        metrics_frame = ai_frame.metrics_frame
        if hasattr(metrics_frame, 'handle_metrics_analysis'):
            asyncio.create_task(self.event_bus.subscribe("metrics_analysis", metrics_frame.handle_metrics_analysis))
        
        logger.info("AI frame handlers setup complete")
        await self._request_initial_ai_data()

    async def _request_initial_ai_data(self):
        """Request initial AI data from the event bus."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized for requesting AI data")
            return
        
        logger.info("Requesting initial AI data")
        try:
            asyncio.create_task(self.event_bus.publish("request_ai_data", {"request": "initial_data"}))
            asyncio.create_task(self.event_bus.publish("request_metrics_data", {"request": "initial_data"}))
            logger.info("Initial AI data requested")
        except Exception as e:
            logger.error(f"Error requesting initial AI data: {e}", exc_info=True)

    async def setup_code_frame_handlers(self, code_frame):
        """Set up event handlers for the code frame."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized in FrameEventManager")
            return
        
        if not hasattr(code_frame, 'code_result_frame') or not hasattr(code_frame, 'templates_frame'):
            logger.error("Code frame components not fully initialized")
            return
        
        logger.info("Setting up code frame handlers")
        self.code_frame = code_frame
        # Code result frame handlers
        code_result_frame = code_frame.code_result_frame
        if hasattr(code_result_frame, 'handle_code_result'):
            asyncio.create_task(self.event_bus.subscribe("code_result", code_result_frame.handle_code_result))
        
        # Templates frame handlers
        templates_frame = code_frame.templates_frame
        if hasattr(templates_frame, 'handle_templates_update'):
            asyncio.create_task(self.event_bus.subscribe("templates_update", templates_frame.handle_templates_update))
        
        logger.info("Code frame handlers setup complete")
        await self._request_initial_code_data()

    async def _request_initial_code_data(self):
        """Request initial code data from the event bus."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized for requesting code data")
            return
        
        logger.info("Requesting initial code data")
        try:
            asyncio.create_task(self.event_bus.publish("request_code_data", {"request": "initial_data"}))
            asyncio.create_task(self.event_bus.publish("request_templates_data", {"request": "initial_data"}))
            logger.info("Initial code data requested")
        except Exception as e:
            logger.error(f"Error requesting initial code data: {e}", exc_info=True)

    async def setup_keys_frame_handlers(self, keys_frame):
        """Set up event handlers for the keys frame."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized in FrameEventManager")
            return
        
        logger.info("Setting up keys frame handlers")
        self.keys_frame = keys_frame
        if hasattr(keys_frame, 'handle_keys_update'):
            asyncio.create_task(self.event_bus.subscribe("keys_update", keys_frame.handle_keys_update))
        
        logger.info("Keys frame handlers setup complete")
        await self._request_initial_keys_data()

    async def _request_initial_keys_data(self):
        """Request initial keys data from the event bus."""
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Event bus not initialized for requesting keys data")
            return
        
        logger.info("Requesting initial keys data")
        try:
            asyncio.create_task(self.event_bus.publish("request_keys_data", {"request": "initial_data"}))
            logger.info("Initial keys data requested")
        except Exception as e:
            logger.error(f"Error requesting initial keys data: {e}", exc_info=True)
