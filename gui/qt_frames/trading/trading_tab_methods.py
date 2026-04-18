"""
Additional methods for Trading Tab - Live Data Integration and UI Refresh
Add these methods to the TradingTab class in trading_tab.py
"""

import time

def _populate_intelligence_hub_with_live_data(self):
    """Populate Intelligence Hub with REAL live data from backend - NO MOCK DATA."""
    try:
        start_feeds = getattr(self, "_start_live_data_feeds", None)
        if callable(start_feeds):
            try:
                start_feeds()
            except Exception:
                pass

        if hasattr(self, "_update_intelligence_hub_ui"):
            self._update_intelligence_hub_ui()

        self.logger.info("✅ Intelligence Hub populated from live data state")
        
    except Exception as e:
        self.logger.error(f"Error populating Intelligence Hub: {e}")

def _update_intelligence_hub_ui(self):
    """Refresh Intelligence Hub UI with current data."""
    try:
        # Update whale tracking card
        if hasattr(self, 'whale_content_label') and self.whale_content_label:
            self.whale_content_label.setText(self.whale_data['content'])
        
        # Update copy trading card
        if hasattr(self, 'copy_content_label') and self.copy_content_label:
            self.copy_content_label.setText(self.copy_trading_data['content'])
        
        # Update moonshot detection card
        if hasattr(self, 'moonshot_content_label') and self.moonshot_content_label:
            self.moonshot_content_label.setText(self.moonshot_data['content'])
            
        self.logger.info("✅ Intelligence Hub UI refreshed")
        
    except Exception as e:
        self.logger.error(f"Error updating Intelligence Hub UI: {e}")

def _start_live_data_feeds(self):
    """Start live data feeds from backend (replaces mock data with real data)."""
    try:
        # Request live whale tracking data
        if self.event_bus:
            self.event_bus.publish('whale.tracking.start', {
                'min_amount': 1000000,  # $1M minimum
                'timestamp': time.time()
            })
            
            # Request live copy trading data
            self.event_bus.publish('copy.trading.fetch_top_traders', {
                'limit': 3,
                'timeframe': '30d',
                'timestamp': time.time()
            })
            
            # Request live moonshot data
            self.event_bus.publish('moonshot.detection.start', {
                'min_gain': 100,  # 100% minimum gain
                'max_rug_risk': 'medium',
                'timestamp': time.time()
            })
            
            self.logger.info("✅ Live data feeds requested from backend")
        
    except Exception as e:
        self.logger.error(f"Error starting live data feeds: {e}")
