"""
Update UI method for TradingFrame.
This contains the _update_ui method that periodically checks Redis connection health
and updates the UI components accordingly.
"""
import tkinter as tk
import logging
import asyncio
from datetime import datetime

class TradingFrameUpdateUI:
    """Contains the update UI method for TradingFrame"""
    
    def _update_ui(self):
        """
        Periodically update the UI based on Redis connection status.
        This method is scheduled to run every 1000ms (1 second).
        It checks Redis connection health and updates UI colors and components.
        """
        try:
            # Check Redis connection health if client exists
            if hasattr(self, 'redis_client') and self.redis_client:
                # Must use async method in sync context - use safe check
                is_healthy = False
                try:
                    # Use create_task instead of direct await since we're in a Tkinter callback
                    if self._event_bus:
                        async def check_health():
                            try:
                                return self.redis_client.is_healthy()
                            except Exception as e:
                                self.logger.error(f"Redis health check failed: {e}")
                                return False
                        
                        # Schedule health check for next event loop cycle
                        future = asyncio.run_coroutine_threadsafe(
                            check_health(), 
                            self._event_bus.get_event_loop()
                        )
                        # Wait with timeout to avoid blocking UI
                        is_healthy = future.result(timeout=0.5)
                    else:
                        is_healthy = False
                except Exception as e:
                    self.logger.warning(f"Error checking Redis health: {e}")
                    is_healthy = False
                
                # Update connection status
                if is_healthy:
                    if not self.redis_connected:
                        self.logger.info("Redis connection restored")
                        self.redis_connected = True
                    
                    self.redis_status_var.set("Connected")
                    self.redis_status.configure(foreground="green")
                    
                    # Enable trading controls if they exist
                    self.trading_enabled = True
                    for widget_name in ['start_button', 'auto_trading_toggle']:
                        if hasattr(self, widget_name) and getattr(self, widget_name):
                            getattr(self, widget_name).configure(state=tk.NORMAL)
                            
                    # Request profit data update on healthy connection
                    if hasattr(self, "safe_publish"):
                        self.safe_publish("trading.request.profit_data", {
                            "timestamp": datetime.now().timestamp()
                        })
                else:
                    if self.redis_connected:
                        self.logger.warning("Redis connection lost")
                        self.redis_connected = False
                        
                        # Schedule async disable trading
                        if self._event_bus:
                            self._event_bus.create_task(
                                self._disable_trading_on_redis_failure("Connection health check failed")
                            )
                    
                    self.redis_status_var.set("Disconnected")
                    self.redis_status.configure(foreground="red")
                    
            # Update Thoth status color based on connection
            if hasattr(self, 'thoth_status_label'):
                if not hasattr(self, '_thoth_last_update'):
                    self._thoth_last_update = datetime.now().timestamp()
                
                current_time = datetime.now().timestamp()
                time_since_update = current_time - self._thoth_last_update
                
                # If no update in 60 seconds, change color to warning
                if time_since_update > 60:
                    self.thoth_status_label.configure(foreground="orange")
                    if time_since_update > 120:  # 2 minutes without update
                        self.thoth_status_label.configure(foreground="red")
                        if self.thoth_status_var.get() != "Disconnected":
                            self.thoth_status_var.set("Disconnected")
                
            # Schedule next update
            self.after(1000, self._update_ui)
            
        except Exception as e:
            self.logger.error(f"Error in UI update cycle: {e}")
            # Ensure we reschedule even on error
            self.after(1000, self._update_ui)
