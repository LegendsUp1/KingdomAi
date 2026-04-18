import asyncio
import logging
import tkinter as tk
from datetime import datetime

class TradingFrameHandlers:
    """
    Event handlers and trading action methods for TradingFrame.
    Includes profit update handlers, Thoth AI command handlers, and trading control methods.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis_connected = False
        self.current_profit = 0.0
        self.current_profit_var = tk.StringVar()
        self.current_profit_var.set("$0.00")
        self.current_profit_label = None
        self.profit_percentage = 0.0
        self.profit_percentage_var = tk.StringVar()
        self.profit_percentage_var.set("0.00%")
        self.profit_goal = 1000000.0  # Default goal of $1M
        self._last_milestone = 0.0
        self.thoth_status_var = tk.StringVar()
        self.thoth_status_var.set("Inactive")
        self.thoth_status_label = None
        self.thoth_controlled = False
        self.trading_status_var = tk.StringVar()
        self.trading_status_var.set("Trading: STOPPED")
        self.trading_status_label = None
        self.auto_trading_var = tk.BooleanVar()
        self.auto_trading_var.set(False)
        self.market_prediction_var = tk.StringVar()
        self.market_prediction_var.set("No prediction available")
        self.market_prediction_label = None
        # UI placeholders
        self.profit_progress = None
        self.start_button = None
        self.pause_button = None
        self.stop_button = None
        self.thoth_insights_text = None
        # Placeholder for safe_publish method
        self.safe_publish = lambda topic, data: None

    def _handle_profit_update(self, data):
        """
        Handle profit updates from Redis and update the UI.
        
        Args:
            data: The profit update data with current_profit
        """
        if not data or 'current_profit' not in data:
            self.logger.warning("Received invalid profit update data")
            return
            
        try:
            # Update profit amount
            self.current_profit = float(data['current_profit'])
            self.current_profit_var.set(f"${self.current_profit:,.2f}")
            
            # Calculate and update percentage
            if self.profit_goal > 0:
                self.profit_percentage = (self.current_profit / self.profit_goal) * 100
                self.profit_percentage_var.set(f"{self.profit_percentage:.2f}%")
                
                # Update progress bar
                if self.profit_progress is not None:
                    self.profit_progress['value'] = min(self.profit_percentage, 100)
            
            # Update color based on profit value
            if self.current_profit_label is not None:
                if self.current_profit < 0:
                    self.current_profit_label.configure(foreground="red")
                else:
                    self.current_profit_label.configure(foreground="green")
                    
            # Log milestone achievements
            if hasattr(self, '_last_milestone'):
                if self._last_milestone < 1000000000 and self.current_profit >= 1000000000:
                    self.logger.info(" MILESTONE: $1 Billion profit achieved!")
                    self._display_ai_insight(" MILESTONE: $1 Billion profit achieved!")
                elif self._last_milestone < 10000000000 and self.current_profit >= 10000000000:
                    self.logger.info(" MILESTONE: $10 Billion profit achieved!")
                    self._display_ai_insight(" MILESTONE: $10 Billion profit achieved!")
                elif self._last_milestone < 100000000000 and self.current_profit >= 100000000000:
                    self.logger.info(" MILESTONE: $100 Billion profit achieved!")
                    self._display_ai_insight(" MILESTONE: $100 Billion profit achieved!")
                elif self._last_milestone < 1000000000000 and self.current_profit >= 1000000000000:
                    self.logger.info(" MILESTONE: $1 Trillion profit achieved!")
                    self._display_ai_insight(" MILESTONE: $1 Trillion profit achieved!")
            
            # Store last milestone for future reference
            self._last_milestone = self.current_profit
                
        except Exception as e:
            self.logger.error(f"Error processing profit update: {str(e)}")

    def _handle_thoth_command(self, data):
        """
        Process commands from Thoth AI for trading control.
        
        Args:
            data: Command data with action and parameters
        """
        if not data or 'action' not in data:
            self.logger.warning("Received invalid Thoth command data")
            return
            
        action = data.get('action', '').lower()
        self.logger.info(f"Received Thoth AI command: {action}")
        
        # Update Thoth control status
        self.thoth_status_var.set("Active - Controlling Trading")
        if self.thoth_status_label is not None:
            self.thoth_status_label.configure(foreground="green")
        self.thoth_controlled = True
        
        # Process command based on action type
        try:
            if action == 'start_trading':
                self._start_trading(thoth_initiated=True)
                self._display_ai_insight(f"Thoth AI initiated trading start at {datetime.now().strftime('%H:%M:%S')}")
                
            elif action == 'pause_trading':
                self._pause_trading(thoth_initiated=True)
                self._display_ai_insight(f"Thoth AI paused trading at {datetime.now().strftime('%H:%M:%S')}")
                
            elif action == 'stop_trading':
                self._stop_trading(thoth_initiated=True)
                self._display_ai_insight(f"Thoth AI stopped trading at {datetime.now().strftime('%H:%M:%S')}")
                
            elif action == 'analyze_market':
                self._request_market_analysis()
                self._display_ai_insight(f"Thoth AI requested market analysis at {datetime.now().strftime('%H:%M:%S')}")
                
            elif action == 'place_order':
                # Extract order details
                symbol = data.get('symbol', 'Unknown')
                quantity = data.get('quantity', 0)
                price = data.get('price', 0)
                order_type = data.get('order_type', 'market')
                
                self._place_thoth_order(symbol, quantity, price, order_type)
                self._display_ai_insight(
                    f"Thoth AI placed {order_type} order: {quantity} {symbol} @ ${price:,.2f}"
                )
                
            else:
                self.logger.warning(f"Unknown Thoth AI command: {action}")
                
        except Exception as e:
            self.logger.error(f"Error processing Thoth command: {str(e)}")

    def _handle_thoth_insight(self, data):
        """
        Display AI insights from Thoth.
        
        Args:
            data: Insight data with insight text
        """
        if not data or 'insight' not in data:
            return
            
        insight = data.get('insight', '')
        timestamp = data.get('timestamp', datetime.now().timestamp())
        time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
        
        self._display_ai_insight(f"[{time_str}] {insight}")

    def _handle_market_prediction(self, data):
        """
        Update market prediction display from Thoth AI.
        
        Args:
            data: Prediction data
        """
        if not data or 'prediction' not in data:
            self.logger.warning("Received invalid market prediction data")
            return
            
        prediction = data.get('prediction', 'N/A')
        direction = data.get('direction', 'neutral').lower()
        confidence = data.get('confidence', 0.0)
        
        self.logger.info(f"Received market prediction: {prediction} ({direction}, {confidence}% confidence)")
        
        # Update prediction variable
        if hasattr(self, 'market_prediction_var'):
            self.market_prediction_var.set(f"{prediction} ({confidence:.1f}%)")
        
        # Update prediction color based on direction
        if hasattr(self, 'market_prediction_label'):
            if direction == 'bullish':
                if self.market_prediction_label is not None:
                    self.market_prediction_label.configure(foreground="green")
            elif direction == 'bearish':
                if self.market_prediction_label is not None:
                    self.market_prediction_label.configure(foreground="red")
            else:
                if self.market_prediction_label is not None:
                    self.market_prediction_label.configure(foreground="yellow")
        
        # Display insight if prediction comes with text
        if 'insight' in data:
            self._display_ai_insight(data['insight'])

    def _toggle_automated_trading(self):
        """Toggle automated trading on/off with Redis integration."""
        if not self.redis_connected:
            self.logger.error("Cannot toggle automated trading: Redis connection required")
            self.auto_trading_var.set(False)
            return
            
        auto_trading_enabled = self.auto_trading_var.get()
        self.logger.info(f"Toggling automated trading: {'ON' if auto_trading_enabled else 'OFF'}")
        
        # Update trading status
        if auto_trading_enabled:
            self.trading_status_var.set("Trading: AUTO")
            if self.trading_status_label is not None:
                self.trading_status_label.configure(foreground="purple")
            
            # Enable buttons for manual override during auto trading
            if self.start_button is not None:
                self.start_button.configure(state=tk.NORMAL)
            if self.pause_button is not None:
                self.pause_button.configure(state=tk.NORMAL)
            if self.stop_button is not None:
                self.stop_button.configure(state=tk.NORMAL)
        else:
            # If turning off auto trading, maintain current status but update color
            if self.trading_status_var.get() == "Trading: AUTO":
                self.trading_status_var.set("Trading: STOPPED")
                if self.trading_status_label is not None:
                    self.trading_status_label.configure(foreground="red")
            
            # Send event to event bus
            if callable(self.safe_publish):
                self.safe_publish("trading.automation", {
                    "enabled": auto_trading_enabled,
                    "timestamp": datetime.now().timestamp(),
                    "source": "trading_frame"
                })

    def _start_trading(self, thoth_initiated=False):
        """
        Start trading with Redis integration.
        
        Args:
            thoth_initiated: Whether this was initiated by Thoth AI
        """
        if not self.redis_connected:
            self.logger.error("Cannot start trading: Redis connection required")
            return
            
        self.logger.info(f"Starting trading (Thoth initiated: {thoth_initiated})")
        
        # Update trading status
        self.trading_status_var.set("Trading: ACTIVE")
        if self.trading_status_label is not None:
            self.trading_status_label.configure(foreground="green")
        
        # Update button states
        if self.start_button is not None:
            self.start_button.configure(state=tk.DISABLED)
        if self.pause_button is not None:
            self.pause_button.configure(state=tk.NORMAL)
        if self.stop_button is not None:
            self.stop_button.configure(state=tk.NORMAL)
        
        # Send event to event bus
        if callable(self.safe_publish):
            self.safe_publish("trading.action", {
                "action": "start",
                "timestamp": datetime.now().timestamp(),
                "thoth_initiated": thoth_initiated,
                "auto_mode": self.auto_trading_var.get(),
                "source": "trading_frame"
            })

    def _pause_trading(self, thoth_initiated=False):
        """
        Pause trading with Redis integration.
        
        Args:
            thoth_initiated: Whether this was initiated by Thoth AI
        """
        if not self.redis_connected:
            self.logger.error("Cannot pause trading: Redis connection required")
            return
            
        self.logger.info(f"Pausing trading (Thoth initiated: {thoth_initiated})")
        
        # Update trading status
        self.trading_status_var.set("Trading: PAUSED")
        if self.trading_status_label is not None:
            self.trading_status_label.configure(foreground="yellow")
        
        # Update button states
        if self.start_button is not None:
            self.start_button.configure(state=tk.NORMAL)
        if self.pause_button is not None:
            self.pause_button.configure(state=tk.DISABLED)
        if self.stop_button is not None:
            self.stop_button.configure(state=tk.NORMAL)
        
        # Send event to event bus
        if callable(self.safe_publish):
            self.safe_publish("trading.action", {
                "action": "pause",
                "timestamp": datetime.now().timestamp(),
                "thoth_initiated": thoth_initiated,
                "auto_mode": self.auto_trading_var.get(),
                "source": "trading_frame"
            })

    def _stop_trading(self, thoth_initiated=False):
        """
        Stop trading with Redis integration.
        
        Args:
            thoth_initiated: Whether this was initiated by Thoth AI
        """
        if not self.redis_connected:
            self.logger.error("Cannot stop trading: Redis connection required")
            return
            
        self.logger.info(f"Stopping trading (Thoth initiated: {thoth_initiated})")
        
        # Update trading status
        self.trading_status_var.set("Trading: STOPPED")
        if self.trading_status_label is not None:
            self.trading_status_label.configure(foreground="red")
        
        # Update button states
        if self.start_button is not None:
            self.start_button.configure(state=tk.NORMAL)
        if self.pause_button is not None:
            self.pause_button.configure(state=tk.DISABLED)
        if self.stop_button is not None:
            self.stop_button.configure(state=tk.DISABLED)
        
        # If auto trading was on, turn it off
        if self.auto_trading_var.get():
            self.auto_trading_var.set(False)
            self._toggle_automated_trading()
        
        # Send event to event bus
        if callable(self.safe_publish):
            self.safe_publish("trading.action", {
                "action": "stop",
                "timestamp": datetime.now().timestamp(),
                "thoth_initiated": thoth_initiated,
                "auto_mode": False,
                "source": "trading_frame"
            })

    def _display_ai_insight(self, insight_text):
        """
        Display an AI insight in the Thoth text area.
        
        Args:
            insight_text: The insight text to display
        """
        if not hasattr(self, "thoth_insights_text") or self.thoth_insights_text is None:
            return
            
        # Enable editing temporarily
        self.thoth_insights_text.config(state=tk.NORMAL)
        
        # Insert new insight at the beginning with timestamp
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.thoth_insights_text.insert('1.0', f"[{timestamp}] {insight_text}\n\n")
        
        # Limit text size (keep last 20 lines)
        content = self.thoth_insights_text.get('1.0', tk.END).split('\n')
        if len(content) > 40:  # 20 insights with blank lines
            self.thoth_insights_text.delete('1.0', tk.END)
            self.thoth_insights_text.insert('1.0', '\n'.join(content[:40]))
        
        # Make read-only again
        self.thoth_insights_text.config(state=tk.DISABLED)
        
        # Scroll to top
        self.thoth_insights_text.yview_moveto(0)

    def _request_market_analysis(self):
        """Request market analysis from Thoth AI via event bus."""
        if not self.redis_connected:
            self.logger.warning("Cannot request market analysis: Redis connection required")
            return
            
        self.logger.debug("Requesting market analysis from Thoth AI")
        
        if callable(self.safe_publish):
            self.safe_publish("thoth.ai.request", {
                "request_type": "market_analysis",
                "timestamp": datetime.now().timestamp(),
                "source": "trading_frame"
            })

    def _place_thoth_order(self, symbol, quantity, price, order_type='market'):
        """
        Place an order via Thoth AI through event bus.
        
        Args:
            symbol: Trading symbol
            quantity: Order quantity
            price: Order price
            order_type: Type of order (market, limit, etc.)
        """
        if not self.redis_connected:
            self.logger.warning(f"Cannot place Thoth order: Redis connection required")
            return
            
        self.logger.info(f"Placing Thoth AI order: {quantity} {symbol} @ ${price:,.2f} ({order_type})")
        
        if callable(self.safe_publish):
            self.safe_publish("trading.order.place", {
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "order_type": order_type,
                "timestamp": datetime.now().timestamp(),
                "source": "thoth_ai",
                "thoth_initiated": True
            })
