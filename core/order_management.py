#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OrderManagement component for handling trading orders across exchanges.
"""

import os
import asyncio
import logging
import json
import uuid
from datetime import datetime
import aiohttp

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class OrderManagement(BaseComponent):
    """
    Component for handling trading orders across multiple exchanges.
    Manages order creation, tracking, and execution.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the OrderManagement component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus, config)
        self.name = "OrderManagement"
        self.description = "Manages trading orders across exchanges"
        
        # Exchange configurations
        self.exchanges = {} if self.config is None else self.config.get("exchanges", {})
        
        # Order settings
        self.default_order_timeout = 60 if self.config is None else self.config.get("default_order_timeout", 60)  # Seconds
        self.max_orders_per_market = 10 if self.config is None else self.config.get("max_orders_per_market", 10)
        self.check_interval = 5.0 if self.config is None else self.config.get("check_interval", 5.0)  # Seconds
        
        # Internal state
        self.session = None
        self.orders = {}  # All orders
        self.pending_orders = {}  # Orders waiting for execution
        self.active_orders = {}  # Orders currently active on exchanges
        self.completed_orders = {}  # Completed/canceled orders
        self.order_check_task = None
        self.is_running = False
        
    async def safe_publish(self, event_name, event_data=None):
        """Safely publish an event to the event bus with error handling.
        
        Args:
            event_name: The name of the event to publish
            event_data: The data to include with the event
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self.event_bus is None:
            logger.warning(f"Cannot publish event {event_name}: Event bus is None")
            return False
            
        try:
            await self.event_bus.publish(event_name, event_data)
            return True
        except Exception as e:
            logger.error(f"Error publishing event {event_name}: {str(e)}")
            return False
    
    async def initialize(self):
        """Initialize the OrderManagement component.
        
        Returns:
            bool: True if initialization was successful
        """
        logger.info("Initializing OrderManagement component")
        
        # Subscribe to relevant events
        if self.event_bus is not None:
            self.event_bus and self.event_bus.subscribe_sync("order.create", self.on_order_create)
            self.event_bus and self.event_bus.subscribe_sync("order.cancel", self.on_order_cancel)
            self.event_bus and self.event_bus.subscribe_sync("order.status", self.on_order_status)
            self.event_bus and self.event_bus.subscribe_sync("order.modify", self.on_order_modify)
            self.event_bus and self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
        else:
            logger.warning("No event bus available, OrderManagement will operate with limited functionality")
        
        # Create HTTP session
        self.session = aiohttp.ClientSession()
        
        # Load saved orders
        await self.load_orders()
        
        # Start order checking task
        self.is_running = True
        self.order_check_task = asyncio.create_task(self.check_orders_loop())
        
        logger.info("OrderManagement component initialized")
        return await asyncio.sleep(0, True) # Return coroutine with bool result
        
    async def load_orders(self):
        """Load saved orders from storage."""
        orders_file = os.path.join(self.config.get("data_dir", "data"), "orders.json")
        
        try:
            if os.path.exists(orders_file):
                with open(orders_file, 'r') as f:
                    orders_data = json.load(f)
                    
                # Load orders into appropriate containers
                self.orders = orders_data.get("all_orders", {})
                self.pending_orders = {k: v for k, v in self.orders.items() 
                                      if v.get("status") == "pending"}
                self.active_orders = {k: v for k, v in self.orders.items() 
                                     if v.get("status") in ["open", "partially_filled"]}
                self.completed_orders = {k: v for k, v in self.orders.items() 
                                        if v.get("status") in ["filled", "canceled", "expired", "rejected"]}
                
                logger.info(f"Loaded {len(self.orders)} orders")
                return True
            else:
                return True
        except Exception as e:
            logger.error(f"Error loading orders: {str(e)}")
            return False
    
    async def save_orders(self):
        """Save orders to storage."""
        orders_file = os.path.join(self.config.get("data_dir", "data"), "orders.json")
        
        try:
            os.makedirs(os.path.dirname(orders_file), exist_ok=True)
            
            # Prepare data for saving
            orders_data = {
                "all_orders": self.orders,
                "last_saved": datetime.now().isoformat()
            }
            
            with open(orders_file, 'w') as f:
                json.dump(orders_data, f, indent=2)
                
            logger.info(f"Saved {len(self.orders)} orders")
        except Exception as e:
            logger.error(f"Error saving orders: {str(e)}")
    
    async def check_orders_loop(self):
        """Continuously check order status at specified interval."""
        try:
            while self.is_running:
                await self.check_pending_orders()
                await self.check_active_orders()
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            logger.info("Order check loop cancelled")
        except Exception as e:
            logger.error(f"Error in order check loop: {str(e)}")
            # Restart the loop
            if self.is_running:
                self.order_check_task = asyncio.create_task(self.check_orders_loop())
    
    async def check_pending_orders(self):
        """Check and process pending orders."""
        for order_id, order in list(self.pending_orders.items()):
            try:
                # Check if order has expired
                if "created_at" in order:
                    created_time = datetime.fromisoformat(order["created_at"])
                    timeout = order.get("timeout", self.default_order_timeout)
                    if (datetime.now() - created_time).total_seconds() > timeout:
                        await self.expire_order(order_id)
                        continue
                
                # Process order
                await self.process_order(order_id, order)
                
            except Exception as e:
                logger.error(f"Error checking pending order {order_id}: {str(e)}")
    
    async def check_active_orders(self):
        """Check status of active orders on exchanges."""
        for order_id, order in list(self.active_orders.items()):
            try:
                exchange = order.get("exchange")
                exchange_order_id = order.get("exchange_order_id")
                
                if not exchange or not exchange_order_id:
                    continue
                
                # Get order status from exchange
                status = await self.get_order_status_from_exchange(exchange, exchange_order_id)
                
                if status:
                    # Update order status
                    await self.update_order_status(order_id, status)
                
            except Exception as e:
                logger.error(f"Error checking active order {order_id}: {str(e)}")
    
    async def process_order(self, order_id, order):
        """
        Process a pending order.
        
        Args:
            order_id: Order ID
            order: Order data
        """
        # Check if order should be executed
        if order.get("status") != "pending":
            return
            
        exchange = order.get("exchange")
        if not exchange:
            await self.reject_order(order_id, "Exchange not specified")
            return
            
        # Submit order to exchange
        result = await self.submit_order_to_exchange(exchange, order)
        
        if result.get("success"):
            # Update order with exchange data
            self.orders[order_id].update({
                "status": "open",
                "exchange_order_id": result.get("exchange_order_id"),
                "submitted_at": datetime.now().isoformat()
            })
            
            # Move order from pending to active
            self.active_orders[order_id] = self.orders[order_id]
            self.pending_orders.pop(order_id, None)
            
            # Publish order status update
            await self.safe_publish("order.status.update", {
                "order_id": order_id,
                "status": "open",
                "exchange_order_id": result.get("exchange_order_id"),
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Order {order_id} submitted successfully to {exchange}")
        else:
            # Reject order
            await self.reject_order(order_id, result.get("error", "Unknown error"))
    
    async def submit_order_to_exchange(self, exchange, order):
        """
        Submit an order to an exchange using ccxt or event_bus exchange connections.
        
        Args:
            exchange: Exchange name
            order: Order data
            
        Returns:
            dict: Submission result
        """
        try:
            # Check if required order data is present
            required_fields = ["market", "side", "type", "amount"]
            missing_fields = [field for field in required_fields if field not in order]
            if missing_fields:
                return {
                    "success": False,
                    "error": f"Missing required order fields: {', '.join(missing_fields)}"
                }
            
            # Try to get exchange client from event_bus first
            exchange_client = None
            if self.event_bus:
                try:
                    # Try to get exchange connector from event bus
                    connector = self.event_bus.get_component("exchange_connector") or self.event_bus.get_component("trading_system")
                    if connector and hasattr(connector, "get_exchange"):
                        exchange_client = connector.get_exchange(exchange)
                    elif connector and hasattr(connector, "exchanges") and exchange in connector.exchanges:
                        exchange_client = connector.exchanges[exchange]
                except Exception as e:
                    logger.debug(f"Could not get exchange from event_bus: {e}")
            
            # If not available from event_bus, try to initialize ccxt directly
            if not exchange_client:
                try:
                    import ccxt
                    exchange_id = exchange.lower()
                    if exchange_id in ccxt.exchanges:
                        # Get API keys from event_bus or config
                        api_key = None
                        api_secret = None
                        if self.event_bus:
                            try:
                                api_manager = self.event_bus.get_component("api_key_manager")
                                if api_manager:
                                    keys = api_manager.get_api_keys(exchange)
                                    api_key = keys.get("api_key") if keys else None
                                    api_secret = keys.get("api_secret") if keys else None
                            except Exception:
                                pass
                        
                        # Fallback to config
                        if not api_key and exchange in self.exchanges:
                            api_key = self.exchanges[exchange].get("api_key")
                            api_secret = self.exchanges[exchange].get("api_secret")
                        
                        if api_key and api_secret:
                            exchange_class = getattr(ccxt, exchange_id)
                            exchange_client = exchange_class({
                                'apiKey': api_key,
                                'secret': api_secret,
                                'enableRateLimit': True,
                                'options': {'defaultType': 'spot'}
                            })
                            exchange_client.load_markets()
                        else:
                            return {
                                "success": False,
                                "error": f"Exchange {exchange} API keys not configured. Configure via event_bus or config."
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"Exchange {exchange} not supported by ccxt"
                        }
                except ImportError:
                    return {
                        "success": False,
                        "error": "ccxt library not installed. Install with: pip install ccxt"
                    }
                except Exception as e:
                    logger.error(f"Error initializing exchange {exchange}: {e}")
                    return {
                        "success": False,
                        "error": f"Failed to initialize exchange: {str(e)}"
                    }
            
            # Submit order using exchange client
            if exchange_client:
                symbol = order.get("market", order.get("symbol"))
                side = order.get("side").lower()  # 'buy' or 'sell'
                order_type = order.get("type", "limit").lower()  # 'market' or 'limit'
                amount = float(order.get("amount"))
                price = float(order.get("price")) if order.get("price") else None
                
                if order_type == "market":
                    result = exchange_client.create_market_order(symbol, side, amount)
                else:
                    if not price:
                        return {
                            "success": False,
                            "error": "Price required for limit orders"
                        }
                    result = exchange_client.create_limit_order(symbol, side, amount, price)
                
                return {
                    "success": True,
                    "exchange_order_id": result.get("id"),
                    "message": "Order submitted successfully",
                    "exchange_response": result
                }
            else:
                return {
                    "success": False,
                    "error": f"Exchange {exchange} client not available"
                }
            
        except Exception as e:
            logger.error(f"Error submitting order to {exchange}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_order_status_from_exchange(self, exchange, exchange_order_id):
        """
        Get order status from exchange using ccxt or event_bus exchange connections.
        
        Args:
            exchange: Exchange name
            exchange_order_id: Exchange order ID
            
        Returns:
            dict: Order status or None if order not found/error
        """
        try:
            # Try to get exchange client from event_bus first
            exchange_client = None
            if self.event_bus:
                try:
                    connector = self.event_bus.get_component("exchange_connector") or self.event_bus.get_component("trading_system")
                    if connector and hasattr(connector, "get_exchange"):
                        exchange_client = connector.get_exchange(exchange)
                    elif connector and hasattr(connector, "exchanges") and exchange in connector.exchanges:
                        exchange_client = connector.exchanges[exchange]
                except Exception as e:
                    logger.debug(f"Could not get exchange from event_bus: {e}")
            
            # If not available from event_bus, try to initialize ccxt directly
            if not exchange_client:
                try:
                    import ccxt
                    exchange_id = exchange.lower()
                    if exchange_id in ccxt.exchanges:
                        # Get API keys from event_bus or config
                        api_key = None
                        api_secret = None
                        if self.event_bus:
                            try:
                                api_manager = self.event_bus.get_component("api_key_manager")
                                if api_manager:
                                    keys = api_manager.get_api_keys(exchange)
                                    api_key = keys.get("api_key") if keys else None
                                    api_secret = keys.get("api_secret") if keys else None
                            except Exception:
                                pass
                        
                        # Fallback to config
                        if not api_key and exchange in self.exchanges:
                            api_key = self.exchanges[exchange].get("api_key")
                            api_secret = self.exchanges[exchange].get("api_secret")
                        
                        if api_key and api_secret:
                            exchange_class = getattr(ccxt, exchange_id)
                            exchange_client = exchange_class({
                                'apiKey': api_key,
                                'secret': api_secret,
                                'enableRateLimit': True
                            })
                            exchange_client.load_markets()
                        else:
                            logger.warning(f"Exchange {exchange} API keys not configured - cannot get order status")
                            return None
                    else:
                        logger.warning(f"Exchange {exchange} not supported by ccxt")
                        return None
                except ImportError:
                    logger.error("ccxt library not installed")
                    return None
                except Exception as e:
                    logger.error(f"Error initializing exchange {exchange}: {e}")
                    return None
            
            # Get order status using exchange client
            if exchange_client:
                try:
                    order_info = exchange_client.fetch_order(exchange_order_id)
                    
                    # Map ccxt order status to our status format
                    ccxt_status = order_info.get("status", "unknown")
                    status_map = {
                        "open": "open",
                        "closed": "filled",
                        "canceled": "canceled",
                        "expired": "expired",
                        "rejected": "rejected"
                    }
                    mapped_status = status_map.get(ccxt_status, ccxt_status)
                    
                    return {
                        "status": mapped_status,
                        "filled": float(order_info.get("filled", 0.0)),
                        "remaining": float(order_info.get("remaining", 0.0)),
                        "average_price": float(order_info.get("average", order_info.get("price", 0.0))),
                        "amount": float(order_info.get("amount", 0.0)),
                        "cost": float(order_info.get("cost", 0.0))
                    }
                except Exception as fetch_error:
                    # Order might not exist or API error
                    logger.debug(f"Error fetching order {exchange_order_id} from {exchange}: {fetch_error}")
                    return None
            else:
                return None
            
        except Exception as e:
            logger.error(f"Error getting order status from {exchange}: {str(e)}")
            return None
    
    async def update_order_status(self, order_id, status_data):
        """
        Update order status.
        
        Args:
            order_id: Order ID
            status_data: Status data from exchange
        """
        if order_id not in self.orders:
            return
            
        current_status = self.orders[order_id].get("status")
        new_status = status_data.get("status")
        
        # Skip if status hasn't changed
        if current_status == new_status:
            return
            
        # Update order with new status
        self.orders[order_id].update({
            "status": new_status,
            "filled": status_data.get("filled", 0.0),
            "remaining": status_data.get("remaining", 1.0),
            "average_price": status_data.get("average_price", 0.0),
            "last_updated": datetime.now().isoformat()
        })
        
        # Move order to appropriate container
        if new_status in ["filled", "canceled", "expired", "rejected"]:
            # Move to completed orders
            self.completed_orders[order_id] = self.orders[order_id]
            self.active_orders.pop(order_id, None)
            self.pending_orders.pop(order_id, None)
        elif new_status in ["open", "partially_filled"]:
            # Move to active orders
            self.active_orders[order_id] = self.orders[order_id]
            self.pending_orders.pop(order_id, None)
        
        # Publish order status update
        await self.safe_publish("order.status.update", {
            "order_id": order_id,
            "status": new_status,
            "filled": status_data.get("filled", 0.0),
            "remaining": status_data.get("remaining", 1.0),
            "average_price": status_data.get("average_price", 0.0),
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Order {order_id} status updated to {new_status}")
        
        # Save orders on status changes
        await self.save_orders()
    
    async def expire_order(self, order_id):
        """
        Mark an order as expired.
        
        Args:
            order_id: Order ID
        """
        if order_id not in self.orders:
            return
            
        # Update order status
        self.orders[order_id].update({
            "status": "expired",
            "last_updated": datetime.now().isoformat()
        })
        
        # Move order to completed orders
        self.completed_orders[order_id] = self.orders[order_id]
        self.active_orders.pop(order_id, None)
        self.pending_orders.pop(order_id, None)
        
        # Publish order status update
        await self.safe_publish("order.status.update", {
            "order_id": order_id,
            "status": "expired",
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Order {order_id} expired")
        
        # Save orders
        await self.save_orders()
    
    async def reject_order(self, order_id, reason):
        """
        Mark an order as rejected.
        
        Args:
            order_id: Order ID
            reason: Rejection reason
        """
        if order_id not in self.orders:
            return
            
        # Update order status
        self.orders[order_id].update({
            "status": "rejected",
            "rejection_reason": reason,
            "last_updated": datetime.now().isoformat()
        })
        
        # Move order to completed orders
        self.completed_orders[order_id] = self.orders[order_id]
        self.active_orders.pop(order_id, None)
        self.pending_orders.pop(order_id, None)
        
        # Publish order status update
        await self.safe_publish("order.status.update", {
            "order_id": order_id,
            "status": "rejected",
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Order {order_id} rejected: {reason}")
        
        # Save orders
        await self.save_orders()
    
    async def create_order(self, order_data):
        """
        Create a new order.
        
        Args:
            order_data: Order data
            
        Returns:
            dict: Order creation result
        """
        try:
            # Validate order data
            required_fields = ["exchange", "market", "side", "type", "amount"]
            missing_fields = [field for field in required_fields if field not in order_data]
            
            if missing_fields:
                return {
                    "success": False,
                    "error": f"Missing required order fields: {', '.join(missing_fields)}"
                }
            
            # Check market order limits
            market = order_data.get("market")
            exchange = order_data.get("exchange")
            market_key = f"{exchange}:{market}"
            
            market_orders = [
                order for order in self.active_orders.values()
                if order.get("exchange") == exchange and order.get("market") == market
            ]
            
            if len(market_orders) >= self.max_orders_per_market:
                return {
                    "success": False,
                    "error": f"Maximum number of orders ({self.max_orders_per_market}) reached for {market_key}"
                }
            
            # Create order ID
            order_id = f"order_{uuid.uuid4().hex}"
            
            # Create order
            self.orders[order_id] = {
                "id": order_id,
                "exchange": order_data.get("exchange"),
                "market": order_data.get("market"),
                "side": order_data.get("side"),
                "type": order_data.get("type"),
                "amount": order_data.get("amount"),
                "price": order_data.get("price"),
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "timeout": order_data.get("timeout", self.default_order_timeout),
                "filled": 0.0,
                "remaining": order_data.get("amount", 0.0),
                "average_price": 0.0,
                "params": order_data.get("params", {})
            }
            
            # Add to pending orders
            self.pending_orders[order_id] = self.orders[order_id]
            
            # Publish order created event
            await self.safe_publish("order.created", {
                "order_id": order_id,
                "order": self.orders[order_id],
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Created order {order_id} for {market_key}")
            
            # Save orders
            await self.save_orders()
            
            return {
                "success": True,
                "order_id": order_id,
                "order": self.orders[order_id]
            }
            
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cancel_order(self, order_id):
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            dict: Cancellation result
        """
        try:
            # Check if order exists
            if order_id not in self.orders:
                return {
                    "success": False,
                    "error": f"Order {order_id} not found"
                }
            
            # Get order
            order = self.orders[order_id]
            
            # Check if order can be canceled
            if order.get("status") in ["filled", "canceled", "expired", "rejected"]:
                return {
                    "success": False,
                    "error": f"Cannot cancel order with status: {order.get('status')}"
                }
            
            # If order is pending, simply mark as canceled
            if order.get("status") == "pending":
                # Update order status
                self.orders[order_id].update({
                    "status": "canceled",
                    "last_updated": datetime.now().isoformat()
                })
                
                # Move order to completed orders
                self.completed_orders[order_id] = self.orders[order_id]
                self.pending_orders.pop(order_id, None)
                
                # Publish order status update
                await self.safe_publish("order.status.update", {
                    "order_id": order_id,
                    "status": "canceled",
                    "timestamp": datetime.now().isoformat()
                })
                
                logger.info(f"Canceled pending order {order_id}")
                
                # Save orders
                await self.save_orders()
                
                return {
                    "success": True,
                    "message": "Order canceled successfully"
                }
            
            # If order is active on exchange, cancel it there
            exchange = order.get("exchange")
            exchange_order_id = order.get("exchange_order_id")
            
            if not exchange or not exchange_order_id:
                return {
                    "success": False,
                    "error": "Order missing exchange information"
                }
            
            # Cancel order on exchange
            result = await self.cancel_order_on_exchange(exchange, exchange_order_id)
            
            if result.get("success"):
                # Update order status
                self.orders[order_id].update({
                    "status": "canceled",
                    "last_updated": datetime.now().isoformat()
                })
                
                # Move order to completed orders
                self.completed_orders[order_id] = self.orders[order_id]
                self.active_orders.pop(order_id, None)
                
                # Publish order status update
                await self.safe_publish("order.status.update", {
                    "order_id": order_id,
                    "status": "canceled",
                    "timestamp": datetime.now().isoformat()
                })
                
                logger.info(f"Canceled active order {order_id} on {exchange}")
                
                # Save orders
                await self.save_orders()
                
                return {
                    "success": True,
                    "message": "Order canceled successfully"
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error")
                }
            
        except Exception as e:
            logger.error(f"Error canceling order {order_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cancel_order_on_exchange(self, exchange, exchange_order_id):
        """
        Cancel an order on an exchange using ccxt or event_bus exchange connections.
        
        Args:
            exchange: Exchange name
            exchange_order_id: Exchange order ID
            
        Returns:
            dict: Cancellation result
        """
        try:
            # Try to get exchange client from event_bus first
            exchange_client = None
            if self.event_bus:
                try:
                    connector = self.event_bus.get_component("exchange_connector") or self.event_bus.get_component("trading_system")
                    if connector and hasattr(connector, "get_exchange"):
                        exchange_client = connector.get_exchange(exchange)
                    elif connector and hasattr(connector, "exchanges") and exchange in connector.exchanges:
                        exchange_client = connector.exchanges[exchange]
                except Exception as e:
                    logger.debug(f"Could not get exchange from event_bus: {e}")
            
            # If not available from event_bus, try to initialize ccxt directly
            if not exchange_client:
                try:
                    import ccxt
                    exchange_id = exchange.lower()
                    if exchange_id in ccxt.exchanges:
                        # Get API keys from event_bus or config
                        api_key = None
                        api_secret = None
                        if self.event_bus:
                            try:
                                api_manager = self.event_bus.get_component("api_key_manager")
                                if api_manager:
                                    keys = api_manager.get_api_keys(exchange)
                                    api_key = keys.get("api_key") if keys else None
                                    api_secret = keys.get("api_secret") if keys else None
                            except Exception:
                                pass
                        
                        # Fallback to config
                        if not api_key and exchange in self.exchanges:
                            api_key = self.exchanges[exchange].get("api_key")
                            api_secret = self.exchanges[exchange].get("api_secret")
                        
                        if api_key and api_secret:
                            exchange_class = getattr(ccxt, exchange_id)
                            exchange_client = exchange_class({
                                'apiKey': api_key,
                                'secret': api_secret,
                                'enableRateLimit': True
                            })
                            exchange_client.load_markets()
                        else:
                            return {
                                "success": False,
                                "error": f"Exchange {exchange} API keys not configured. Configure via event_bus or config."
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"Exchange {exchange} not supported by ccxt"
                        }
                except ImportError:
                    return {
                        "success": False,
                        "error": "ccxt library not installed. Install with: pip install ccxt"
                    }
                except Exception as e:
                    logger.error(f"Error initializing exchange {exchange}: {e}")
                    return {
                        "success": False,
                        "error": f"Failed to initialize exchange: {str(e)}"
                    }
            
            # Cancel order using exchange client
            if exchange_client:
                try:
                    result = exchange_client.cancel_order(exchange_order_id)
                    return {
                        "success": True,
                        "message": "Order canceled successfully",
                        "exchange_response": result
                    }
                except Exception as cancel_error:
                    # Order might already be filled or not exist
                    error_msg = str(cancel_error)
                    if "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                        return {
                            "success": False,
                            "error": f"Order {exchange_order_id} not found (may already be filled or canceled)"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Failed to cancel order: {error_msg}"
                        }
            else:
                return {
                    "success": False,
                    "error": f"Exchange {exchange} client not available"
                }
            
        except Exception as e:
            logger.error(f"Error canceling order on {exchange}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_order(self, order_id):
        """
        Get order details.
        
        Args:
            order_id: Order ID
            
        Returns:
            dict: Order details
        """
        if order_id in self.orders:
            return {
                "success": True,
                "order": self.orders[order_id]
            }
        else:
            return {
                "success": False,
                "error": f"Order {order_id} not found"
            }
    
    async def get_orders(self, filters=None):
        """
        Get orders with optional filtering.
        
        Args:
            filters: Filter criteria
            
        Returns:
            dict: Filtered orders
        """
        filters = filters or {}
        
        try:
            # Start with all orders
            result = self.orders
            
            # Apply filters
            if "status" in filters:
                status = filters["status"]
                if status == "pending":
                    result = self.pending_orders
                elif status == "active":
                    result = self.active_orders
                elif status == "completed":
                    result = self.completed_orders
                else:
                    result = {k: v for k, v in result.items() if v.get("status") == status}
            
            if "exchange" in filters:
                exchange = filters["exchange"]
                result = {k: v for k, v in result.items() if v.get("exchange") == exchange}
            
            if "market" in filters:
                market = filters["market"]
                result = {k: v for k, v in result.items() if v.get("market") == market}
            
            if "side" in filters:
                side = filters["side"]
                result = {k: v for k, v in result.items() if v.get("side") == side}
            
            if "since" in filters:
                since = filters["since"]
                result = {k: v for k, v in result.items() 
                          if v.get("created_at", "0") >= since}
            
            # Apply limit if specified
            if "limit" in filters and isinstance(filters["limit"], int):
                limit = filters["limit"]
                # Sort by created_at in descending order
                sorted_items = sorted(
                    result.items(),
                    key=lambda x: x[1].get("created_at", "0"),
                    reverse=True
                )
                result = dict(sorted_items[:limit])
            
            return {
                "success": True,
                "orders": result,
                "count": len(result)
            }
            
        except Exception as e:
            logger.error(f"Error getting orders: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def on_order_create(self, data):
        """
        Handle order create event.
        
        Args:
            data: Order creation data
        """
        request_id = data.get("request_id")
        order_data = data.get("order", {})
        
        result = await self.create_order(order_data)
        
        # Publish result
        await self.safe_publish("order.create.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_order_cancel(self, data):
        """
        Handle order cancel event.
        
        Args:
            data: Order cancellation data
        """
        request_id = data.get("request_id")
        order_id = data.get("order_id")
        
        if not order_id:
            result = {
                "success": False,
                "error": "Order ID not specified"
            }
        else:
            result = await self.cancel_order(order_id)
        
        # Publish result
        await self.safe_publish("order.cancel.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_order_status(self, data):
        """
        Handle order status event.
        
        Args:
            data: Order status request data
        """
        request_id = data.get("request_id")
        order_id = data.get("order_id")
        
        if not order_id:
            result = {
                "success": False,
                "error": "Order ID not specified"
            }
        else:
            result = await self.get_order(order_id)
        
        # Publish result
        await self.safe_publish("order.status.result", {
            "request_id": request_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_order_modify(self, data):
        """
        Handle order modify event.
        
        Args:
            data: Order modification data
        """
        request_id = data.get("request_id")
        order_id = data.get("order_id")
        modifications = data.get("modifications", {})

        try:
            if order_id and order_id in getattr(self, '_active_orders', {}):
                order = self._active_orders[order_id]
                for key, value in modifications.items():
                    if key in ("price", "quantity", "stop_loss", "take_profit"):
                        order[key] = value
                self._active_orders[order_id] = order
                await self.safe_publish("order.modify.result", {
                    "request_id": request_id,
                    "result": {"success": True, "order_id": order_id, "modifications": modifications},
                    "timestamp": datetime.now().isoformat()
                })
            else:
                await self.safe_publish("order.modify.result", {
                    "request_id": request_id,
                    "result": {"success": False, "error": f"Order {order_id} not found"},
                    "timestamp": datetime.now().isoformat()
                })
        except Exception as e:
            await self.safe_publish("order.modify.result", {
                "request_id": request_id,
                "result": {"success": False, "error": str(e)},
                "timestamp": datetime.now().isoformat()
            })
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the OrderManagement component."""
        logger.info("Shutting down OrderManagement component")
        
        # Stop order checking
        self.is_running = False
        if self.order_check_task and not self.order_check_task.done():
            self.order_check_task.cancel()
            try:
                await self.order_check_task
            except asyncio.CancelledError:
                pass
        
        # Save final order state
        await self.save_orders()
        
        # Close HTTP session
        if self.session:
            await self.session.close()
        
        logger.info("OrderManagement component shut down successfully")
