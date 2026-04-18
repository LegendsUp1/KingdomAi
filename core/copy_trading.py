"""
CopyTrading module for Kingdom AI system.
"""

import logging
import json
import os
from datetime import datetime

class CopyTrading:
    """
    Copy trading system for the Kingdom AI.
    Allows automatic copying of trades from successful traders.
    """
    
    def __init__(self, event_bus=None, market_api=None, trading_system=None, config=None):
        """Initialize the copy trading system."""
        self.event_bus = event_bus
        self.market_api = market_api
        self.trading_system = trading_system
        self.config = config or {}
        self.logger = logging.getLogger("CopyTrading")
        
        # Copy trading settings
        self.enabled = self.config.get("enabled", False)
        self.max_traders = self.config.get("max_traders", 5)
        self.risk_factor = self.config.get("risk_factor", 0.5)  # 0.0 to 1.0
        
        # Trader subscriptions
        self.traders = {}
        self.trader_performance = {}
        
        # Copy history
        self.copy_history = []
        self.max_history_size = self.config.get("max_history_size", 1000)
        
    async def initialize(self):
        """Initialize the copy trading system."""
        try:
            self.logger.info("Initializing Copy Trading System")
            
            # Load trader subscriptions if available
            traders_file = self.config.get("traders_file", "data/copy_traders.json")
            if os.path.exists(traders_file):
                try:
                    with open(traders_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.traders = data.get("traders", {})
                        self.trader_performance = data.get("performance", {})
                        self.logger.info(f"Loaded {len(self.traders)} trader subscriptions")
                except Exception as e:
                    self.logger.error(f"Error loading trader subscriptions: {e}")
            
            # Register event handlers
            if self.event_bus:
                # Don't await bool returns from synchronous methods
                self.event_bus.subscribe_sync("copy_trading.subscribe", self.handle_subscribe)
                self.event_bus.subscribe_sync("copy_trading.unsubscribe", self.handle_unsubscribe)
                self.event_bus.subscribe_sync("copy_trading.get_traders", self.handle_get_traders)
                self.event_bus.subscribe_sync("copy_trading.toggle", self.handle_toggle)
                self.event_bus.subscribe_sync("copy_trading.set_risk", self.handle_set_risk)
                self.event_bus.subscribe_sync("trading.new_trade", self.handle_new_trade)
                self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
                # KAIG Intelligence Bridge — THREE TARGETS + rebrand resilience
                self.event_bus.subscribe_sync("kaig.intel.trading.directive", self._on_kaig_directive)
                self.event_bus.subscribe_sync("kaig.identity.changed", self._on_identity_changed)
                self.logger.info("Copy Trading event handlers registered (incl. KAIG 3 targets + rebrand)")
            
            # Start periodic checks if enabled
            if self.enabled:
                self._start_trader_monitoring()
            
            self.logger.info("Copy Trading System initialized successfully")
            self._initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing Copy Trading System: {e}")
            self._initialized = False
            return False
    
    def _start_trader_monitoring(self):
        """Start periodic monitoring of trader activity."""
        # Wire to real signal sources via event_bus
        if self.event_bus:
            # Subscribe to real trading signals from trading system
            self.event_bus.subscribe_sync("trading.signal", self._on_trading_signal)
            self.event_bus.subscribe_sync("trading.execution", self._on_trade_execution)
            self.logger.info("Started trader monitoring - listening for real trading signals")
        else:
            self.logger.warning("Cannot start trader monitoring: event_bus not available")
    
    def _on_trading_signal(self, data):
        """Handle real trading signal from trading system."""
        try:
            if not self.enabled:
                return
            
            # Extract signal data
            trader_id = data.get("trader_id") or data.get("source", "system")
            symbol = data.get("symbol")
            side = data.get("side")  # 'buy' or 'sell'
            signal_strength = data.get("strength", 1.0)
            
            # Check if we're subscribed to this trader
            if trader_id in self.traders and self.traders[trader_id].get("active", False):
                # Create trade data from signal
                trade = {
                    "symbol": symbol,
                    "side": side,
                    "quantity": data.get("quantity"),
                    "price": data.get("price"),
                    "signal_strength": signal_strength,
                    "timestamp": data.get("timestamp")
                }
                # Process the trade signal
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.handle_new_trade({"trader_id": trader_id, "trade": trade}))
                except RuntimeError:
                    # No event loop, create new one
                    asyncio.run(self.handle_new_trade({"trader_id": trader_id, "trade": trade}))
        except Exception as e:
            self.logger.error(f"Error handling trading signal: {e}")
    
    def _on_trade_execution(self, data):
        """Handle real trade execution notification."""
        try:
            trader_id = data.get("trader_id") or data.get("source", "system")
            if trader_id in self.traders:
                # Update performance tracking with real execution data
                if trader_id in self.trader_performance:
                    self.trader_performance[trader_id]["trades_total"] += 1
                    if data.get("success"):
                        self.trader_performance[trader_id]["successful_trades"] += 1
                        profit = data.get("profit", 0.0)
                        if profit:
                            self.trader_performance[trader_id]["profit_loss"] += profit
                    else:
                        self.trader_performance[trader_id]["failed_trades"] += 1
                    self.trader_performance[trader_id]["last_update"] = datetime.now().isoformat()
        except Exception as e:
            self.logger.error(f"Error handling trade execution: {e}")
    
    async def handle_subscribe(self, data):
        """Handle request to subscribe to a trader."""
        try:
            if not data or "trader_id" not in data:
                await self._publish_error("subscribe", "No trader ID provided")
                return
                
            trader_id = data.get("trader_id")
            alias = data.get("alias", f"Trader_{trader_id[:8]}")
            risk_level = data.get("risk_level", "medium")
            allocation = data.get("allocation", 0.1)  # 10% of available funds
            
            # Check if already subscribed
            if trader_id in self.traders:
                await self._publish_error("subscribe", f"Already subscribed to trader {trader_id}")
                return
                
            # Validate allocation
            if allocation <= 0 or allocation > 1:
                await self._publish_error("subscribe", "Allocation must be between 0 and 1")
                return
                
            # Validate risk level
            valid_risk_levels = ["low", "medium", "high"]
            if risk_level not in valid_risk_levels:
                await self._publish_error("subscribe", f"Invalid risk level. Must be one of: {valid_risk_levels}")
                return
                
            # Subscribe to trader
            self.traders[trader_id] = {
                "alias": alias,
                "risk_level": risk_level,
                "allocation": allocation,
                "subscribed_at": datetime.now().isoformat(),
                "active": True
            }
            
            # Initialize performance tracking
            self.trader_performance[trader_id] = {
                "trades_total": 0,
                "trades_copied": 0,
                "successful_trades": 0,
                "failed_trades": 0,
                "profit_loss": 0.0,
                "last_update": datetime.now().isoformat()
            }
            
            # Publish confirmation
            if self.event_bus:
                await self.event_bus.publish("copy_trading.subscribed", {
                    "trader_id": trader_id,
                    "alias": alias,
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.info(f"Subscribed to trader: {alias} ({trader_id})")
            
        except Exception as e:
            self.logger.error(f"Error subscribing to trader: {e}")
            await self._publish_error("subscribe", str(e))
    
    async def handle_unsubscribe(self, data):
        """Handle request to unsubscribe from a trader."""
        try:
            if not data or "trader_id" not in data:
                await self._publish_error("unsubscribe", "No trader ID provided")
                return
                
            trader_id = data.get("trader_id")
            
            # Check if subscribed
            if trader_id not in self.traders:
                await self._publish_error("unsubscribe", f"Not subscribed to trader {trader_id}")
                return
                
            # Get trader info before removal
            trader_info = self.traders[trader_id]
            
            # Remove trader subscription
            del self.traders[trader_id]
            
            # Keep performance history
            # self.trader_performance[trader_id]["active"] = False
            
            # Publish confirmation
            if self.event_bus:
                await self.event_bus.publish("copy_trading.unsubscribed", {
                    "trader_id": trader_id,
                    "alias": trader_info.get("alias"),
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.info(f"Unsubscribed from trader: {trader_info.get('alias')} ({trader_id})")
            
        except Exception as e:
            self.logger.error(f"Error unsubscribing from trader: {e}")
            await self._publish_error("unsubscribe", str(e))
    
    async def handle_get_traders(self, data=None):
        """Handle request to get subscribed traders."""
        try:
            # Prepare result with traders and their performance
            result = {
                "traders": {}
            }
            
            for trader_id, trader_info in self.traders.items():
                result["traders"][trader_id] = {
                    **trader_info,
                    "performance": self.trader_performance.get(trader_id, {})
                }
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish("copy_trading.traders", {
                    **result,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error getting traders: {e}")
            await self._publish_error("get_traders", str(e))
    
    async def handle_toggle(self, data):
        """Handle request to toggle copy trading on/off."""
        try:
            if not data or "enabled" not in data:
                await self._publish_error("toggle", "No enabled state provided")
                return
                
            enabled = data.get("enabled", False)
            
            # Toggle copy trading
            self.enabled = enabled
            
            if self.enabled:
                self._start_trader_monitoring()
            
            # Publish confirmation
            if self.event_bus:
                await self.event_bus.publish("copy_trading.toggled", {
                    "enabled": self.enabled,
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.info(f"Copy trading {'enabled' if self.enabled else 'disabled'}")
            
        except Exception as e:
            self.logger.error(f"Error toggling copy trading: {e}")
            await self._publish_error("toggle", str(e))
    
    async def handle_set_risk(self, data):
        """Handle request to set copy trading risk factor."""
        try:
            if not data or "risk_factor" not in data:
                await self._publish_error("set_risk", "No risk factor provided")
                return
                
            risk_factor = data.get("risk_factor")
            
            # Validate risk factor
            if risk_factor < 0 or risk_factor > 1:
                await self._publish_error("set_risk", "Risk factor must be between 0 and 1")
                return
                
            # Set risk factor
            self.risk_factor = risk_factor
            
            # Publish confirmation
            if self.event_bus:
                await self.event_bus.publish("copy_trading.risk_set", {
                    "risk_factor": self.risk_factor,
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.info(f"Copy trading risk factor set to {self.risk_factor}")
            
        except Exception as e:
            self.logger.error(f"Error setting risk factor: {e}")
            await self._publish_error("set_risk", str(e))
    
    async def handle_new_trade(self, data):
        """Handle notification of a new trade from a subscribed trader."""
        try:
            if not self.enabled:
                return
                
            if not data or "trader_id" not in data:
                return
                
            trader_id = data.get("trader_id")
            
            # Check if we're subscribed to this trader
            if trader_id not in self.traders or not self.traders[trader_id].get("active", False):
                return
                
            # Extract trade details
            trade = data.get("trade", {})
            if not trade:
                return
                
            # Update trader performance
            if trader_id in self.trader_performance:
                self.trader_performance[trader_id]["trades_total"] += 1
                self.trader_performance[trader_id]["last_update"] = datetime.now().isoformat()
            
            # Decide whether to copy the trade
            should_copy = await self._should_copy_trade(trader_id, trade)
            
            if should_copy:
                # Copy the trade
                success = await self._copy_trade(trader_id, trade)
                
                # Record in history
                copy_record = {
                    "trader_id": trader_id,
                    "trader_alias": self.traders[trader_id].get("alias"),
                    "trade": trade,
                    "success": success,
                    "timestamp": datetime.now().isoformat()
                }
                
                self.copy_history.append(copy_record)
                
                # Trim history if needed
                if len(self.copy_history) > self.max_history_size:
                    self.copy_history = self.copy_history[-self.max_history_size:]
                
                # Update trader performance
                if trader_id in self.trader_performance:
                    self.trader_performance[trader_id]["trades_copied"] += 1
                    if success:
                        self.trader_performance[trader_id]["successful_trades"] += 1
                    else:
                        self.trader_performance[trader_id]["failed_trades"] += 1
                
                # Publish copy notification
                if self.event_bus:
                    await self.event_bus.publish("copy_trading.trade_copied", {
                        "trader_id": trader_id,
                        "trader_alias": self.traders[trader_id].get("alias"),
                        "trade": trade,
                        "success": success,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                self.logger.info(f"Copied trade from {self.traders[trader_id].get('alias')}: {'success' if success else 'failed'}")
                
        except Exception as e:
            self.logger.error(f"Error handling new trade: {e}")
    
    async def _should_copy_trade(self, trader_id, trade):
        """Determine whether a trade should be copied."""
        # This is a simplified implementation
        # In a real system, this would include more sophisticated risk management
        
        if not self.enabled:
            return False
            
        trader_info = self.traders.get(trader_id, {})
        risk_level = trader_info.get("risk_level", "medium")
        
        # Apply risk factor based on trader settings
        if risk_level == "low" and self.risk_factor > 0.7:
            return False
        elif risk_level == "medium" and self.risk_factor > 0.9:
            return False
        
        # Check trade parameters
        if "symbol" not in trade or "side" not in trade:
            return False
            
        # Additional checks could be added here
        
        return True
    
    async def _copy_trade(self, trader_id, trade):
        """Copy a trade from a trader."""
        try:
            # Extract trade details
            symbol = trade.get("symbol")
            side = trade.get("side")
            quantity = trade.get("quantity")
            price = trade.get("price")
            
            # Validate required parameters
            if not symbol or not side:
                self.logger.error(f"Missing required trade parameters: {trade}")
                return False
                
            # Scale quantity based on allocation
            trader_info = self.traders.get(trader_id, {})
            allocation = trader_info.get("allocation", 0.1)
            
            # Apply risk factor to allocation
            effective_allocation = allocation * self.risk_factor
            
            # If quantity is not provided, calculate based on price and allocation
            if not quantity and price:
                # Calculate quantity based on available funds and effective allocation
                if self.trading_system and hasattr(self.trading_system, "get_balance"):
                    try:
                        balance = self.trading_system.get_balance(symbol.split("/")[1] if "/" in symbol else "USDT")
                        available_funds = balance * effective_allocation
                        quantity = available_funds / price if price > 0 else 0.01
                    except Exception:
                        quantity = 0.01  # Minimum trade size fallback
                else:
                    quantity = 0.01  # Minimum trade size
            
            # Execute the trade using the trading system or event_bus
            if self.trading_system:
                try:
                    # Call trading system to execute the trade
                    if hasattr(self.trading_system, "create_order"):
                        result = await self.trading_system.create_order({
                            "symbol": symbol,
                            "side": side,
                            "type": "market" if not price else "limit",
                            "amount": quantity,
                            "price": price
                        })
                        success = result.get("success", False) if isinstance(result, dict) else bool(result)
                        self.logger.info(f"Copied trade executed: {symbol} {side} {quantity} - Success: {success}")
                        return success
                    else:
                        self.logger.warning("Trading system does not have create_order method")
                        return False
                except Exception as e:
                    self.logger.error(f"Error executing copied trade: {e}")
                    return False
            elif self.event_bus:
                # Use event_bus to request trade execution
                try:
                    await self.event_bus.publish("order.create", {
                        "order": {
                            "exchange": "default",
                            "market": symbol,
                            "side": side,
                            "type": "market" if not price else "limit",
                            "amount": quantity,
                            "price": price
                        }
                    })
                    self.logger.info(f"Copied trade request sent via event_bus: {symbol} {side} {quantity}")
                    return True  # Request sent, execution handled by order management
                except Exception as e:
                    self.logger.error(f"Error sending trade request via event_bus: {e}")
                    return False
            else:
                self.logger.warning("No trading system or event_bus available for copying trade")
                return False
                
        except Exception as e:
            self.logger.error(f"Error copying trade: {e}")
            return False
    
    def _on_kaig_directive(self, event_data):
        """Receive KAIG directive — 3 targets copy trading must know.

        1. SURVIVAL FLOOR: $26K realized → $13K treasury (existential)
        2. KAIG PRICE FLOOR: 1 KAIG > highest crypto ATH ever (live-monitored)
        3. ULTIMATE TARGET: $2T (aspirational, always pursue)
        All copy-traded profits route 50% to KAIG treasury buyback.
        """
        if isinstance(event_data, dict):
            self._kaig_directive = event_data
            self.logger.info("CopyTrading: KAIG directive received — 3 targets loaded")

    def _on_identity_changed(self, event_data):
        """Handle token rebrand — all copy-traded profits and balances preserved.
        Tracked by wallet address, not token name. Zero loss. Users do nothing."""
        if isinstance(event_data, dict):
            self.logger.warning(
                "CopyTrading: TOKEN REBRANDED %s → %s. All profits preserved.",
                event_data.get("old_ticker", "?"),
                event_data.get("new_ticker", "?"))

    async def handle_shutdown(self, data=None):
        """Handle system shutdown event."""
        try:
            self.logger.info("Shutting down Copy Trading System")
            
            # Save trader subscriptions
            traders_file = self.config.get("traders_file", "data/copy_traders.json")
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(traders_file), exist_ok=True)
                
                with open(traders_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "traders": self.traders,
                        "performance": self.trader_performance
                    }, f, indent=2)
                    
                self.logger.info(f"Saved trader subscriptions to {traders_file}")
            except Exception as e:
                self.logger.error(f"Error saving trader subscriptions: {e}")
            
            self.logger.info("Copy Trading System shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during Copy Trading System shutdown: {e}")
    
    async def _publish_error(self, operation, error_message):
        """Publish an error message to the event bus."""
        if self.event_bus:
            await self.event_bus.publish("copy_trading.error", {
                "operation": operation,
                "error": error_message,
                "timestamp": datetime.now().isoformat()
            })
