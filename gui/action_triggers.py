#!/usr/bin/env python3
"""
Kingdom AI Action Triggers Module

This module implements action triggers for handling user interactions
and connecting UI events to the event bus and component actions.
"""

import logging
import traceback
import threading
from datetime import datetime
import time

logger = logging.getLogger("KingdomAI.ActionTriggers")

class ActionTriggers:
    """
    Action triggers for handling user interactions.
    
    This class provides a centralized way to connect UI events (button clicks,
    menu selections, etc.) to actions in the application, including sending
    events to the event bus, updating component state, and performing operations.
    """
    
    def __init__(self, event_bus=None, gui_binder=None):
        """Initialize the action triggers"""
        self.event_bus = event_bus
        self.gui_binder = gui_binder
        self.actions = {}
        self.running_actions = {}
        
        self.logger = logger
        self.logger.info("Action Triggers initialized")
    
    def register_action(self, action_id, action_func, category="general"):
        """Register an action function"""
        self.actions[action_id] = {
            "func": action_func,
            "category": category
        }
        
        self.logger.info(f"Registered action: {action_id} (category: {category})")
        
        # Return the action ID for reference
        return action_id
    
    def get_action(self, action_id):
        """Get an action function by ID"""
        if action_id in self.actions:
            return self.actions[action_id]["func"]
        return None
    
    def trigger_action(self, action_id, *args, **kwargs):
        """Trigger an action by ID"""
        if action_id in self.actions:
            try:
                action_func = self.actions[action_id]["func"]
                result = action_func(*args, **kwargs)
                
                self.logger.info(f"Triggered action: {action_id}")
                return result
            except Exception as e:
                self.logger.error(f"Error triggering action {action_id}: {e}")
                self.logger.error(traceback.format_exc())
                
                # Publish error event
                if self.event_bus:
                    self.event_bus.publish("error", {
                        "type": "action_error",
                        "action": action_id,
                        "message": str(e),
                        "traceback": traceback.format_exc()
                    })
                
                return None
        else:
            self.logger.warning(f"Cannot trigger action {action_id}: Not registered")
            return None
    
    def trigger_action_async(self, action_id, callback=None, *args, **kwargs):
        """Trigger an action asynchronously"""
        if action_id in self.actions:
            # Create a thread to run the action
            thread = threading.Thread(
                target=self._run_async_action,
                args=(action_id, callback, args, kwargs),
                daemon=True
            )
            
            # Store the thread
            self.running_actions[action_id] = thread
            
            # Start the thread
            thread.start()
            
            self.logger.info(f"Triggered async action: {action_id}")
            return True
        else:
            self.logger.warning(f"Cannot trigger async action {action_id}: Not registered")
            return False
    
    def _run_async_action(self, action_id, callback, args, kwargs):
        """Run an action asynchronously"""
        try:
            # Get the action function
            action_func = self.actions[action_id]["func"]
            
            # Run the action
            result = action_func(*args, **kwargs)
            
            # Call the callback if provided
            if callback:
                callback(action_id, result, None)
            
            # Publish completion event
            if self.event_bus:
                self.event_bus.publish("action.completed", {
                    "action_id": action_id,
                    "result": result
                })
            
            self.logger.info(f"Completed async action: {action_id}")
        except Exception as e:
            self.logger.error(f"Error in async action {action_id}: {e}")
            self.logger.error(traceback.format_exc())
            
            # Call the callback with the error if provided
            if callback:
                callback(action_id, None, str(e))
            
            # Publish error event
            if self.event_bus:
                self.event_bus.publish("error", {
                    "type": "action_error",
                    "action": action_id,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                })
        
        # Remove the thread from running actions
        if action_id in self.running_actions:
            del self.running_actions[action_id]
    
    # Button/UI Event Actions
    
    def create_button_action(self, action_id, event_type, event_data=None):
        """Create a button action that publishes an event"""
        def button_action():
            if self.event_bus:
                self.event_bus.publish(event_type, event_data or {})
                self.logger.info(f"Button action {action_id} published event: {event_type}")
            else:
                self.logger.warning(f"Button action {action_id} failed: No event bus")
        
        # Register the action
        self.register_action(action_id, button_action, "button")
        
        return button_action
    
    def create_tab_change_action(self, tab_id):
        """Create an action for tab change"""
        def tab_change_action():
            if self.event_bus:
                self.event_bus.publish("gui.tab_changed", {
                    "tab_id": tab_id
                })
                self.logger.info(f"Tab changed to: {tab_id}")
        
        # Register the action
        action_id = f"tab_change_{tab_id}"
        self.register_action(action_id, tab_change_action, "tab")
        
        return tab_change_action
    
    # Trading Actions
    
    def create_trade_action(self, action_type, symbol, amount=None, price=None):
        """Create a trading action"""
        def trade_action():
            trade_data = {
                "action": action_type,
                "symbol": symbol
            }
            
            if amount is not None:
                trade_data["amount"] = amount
            
            if price is not None:
                trade_data["price"] = price
            
            if self.event_bus:
                self.event_bus.publish("trading.request", trade_data)
                self.logger.info(f"Trade action: {action_type} {symbol}")
            else:
                self.logger.warning(f"Trade action failed: No event bus")
        
        # Register the action
        action_id = f"trade_{action_type}_{symbol}"
        self.register_action(action_id, trade_action, "trading")
        
        return trade_action
    
    # Mining Actions
    
    def create_mining_action(self, action_type, pool=None, miner=None):
        """Create a mining action"""
        def mining_action():
            mining_data = {
                "action": action_type
            }
            
            if pool is not None:
                mining_data["pool"] = pool
            
            if miner is not None:
                mining_data["miner"] = miner
            
            if self.event_bus:
                self.event_bus.publish("mining.request", mining_data)
                self.logger.info(f"Mining action: {action_type}")
            else:
                self.logger.warning(f"Mining action failed: No event bus")
        
        # Register the action
        action_id = f"mining_{action_type}"
        self.register_action(action_id, mining_action, "mining")
        
        return mining_action
    
    # Wallet Actions
    
    def create_wallet_action(self, action_type, coin=None, address=None, amount=None):
        """Create a wallet action"""
        def wallet_action():
            wallet_data = {
                "action": action_type
            }
            
            if coin is not None:
                wallet_data["coin"] = coin
            
            if address is not None:
                wallet_data["address"] = address
            
            if amount is not None:
                wallet_data["amount"] = amount
            
            if self.event_bus:
                self.event_bus.publish("wallet.request", wallet_data)
                self.logger.info(f"Wallet action: {action_type}")
            else:
                self.logger.warning(f"Wallet action failed: No event bus")
        
        # Register the action
        action_id = f"wallet_{action_type}"
        self.register_action(action_id, wallet_action, "wallet")
        
        return wallet_action
    
    # ThothAI Actions
    
    def create_thoth_action(self, action_type, message=None, model=None):
        """Create a ThothAI action"""
        def thoth_action():
            thoth_data = {
                "action": action_type
            }
            
            if message is not None:
                thoth_data["message"] = message
            
            if model is not None:
                thoth_data["model"] = model
            
            if self.event_bus:
                self.event_bus.publish("thoth.request", thoth_data)
                self.logger.info(f"ThothAI action: {action_type}")
            else:
                self.logger.warning(f"ThothAI action failed: No event bus")
        
        # Register the action
        action_id = f"thoth_{action_type}"
        self.register_action(action_id, thoth_action, "thoth")
        
        return thoth_action
    
    # API Key Actions
    
    def create_api_key_action(self, action_type, platform=None, key=None, secret=None):
        """Create an API key action"""
        def api_key_action():
            api_key_data = {
                "action": action_type
            }
            
            if platform is not None:
                api_key_data["platform"] = platform
            
            if key is not None:
                api_key_data["key"] = key
            
            if secret is not None:
                api_key_data["secret"] = secret
            
            if self.event_bus:
                self.event_bus.publish("api_key.request", api_key_data)
                self.logger.info(f"API key action: {action_type}")
            else:
                self.logger.warning(f"API key action failed: No event bus")
        
        # Register the action
        action_id = f"api_key_{action_type}"
        self.register_action(action_id, api_key_action, "api_key")
        
        return api_key_action

# Singleton instance for global access
_instance = None

def get_instance(event_bus=None, gui_binder=None):
    """Get the singleton instance of the action triggers"""
    global _instance
    if _instance is None:
        _instance = ActionTriggers(event_bus, gui_binder)
    return _instance
