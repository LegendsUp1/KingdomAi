#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MemeCoins component for tracking and analyzing meme cryptocurrencies.
"""

import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
import aiohttp
import re

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class MemeCoins(BaseComponent):
    """
    Component for tracking and analyzing meme cryptocurrencies.
    Monitors social media trends, trading volumes, and market sentiment.
    """
    
    def __init__(self, event_bus=None, config=None):
        """
        Initialize the MemeCoins component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(name="MemeCoins", event_bus=event_bus, config=config)
        self.name = "MemeCoins"
        self.description = "Tracks and analyzes meme cryptocurrencies"
        
        # API configuration
        self.coingecko_api_url = self.config.get("coingecko_api_url", "https://api.coingecko.com/api/v3")
        self.twitter_api_key = self.config.get("twitter_api_key", os.environ.get("TWITTER_API_KEY", ""))
        self.reddit_api_key = self.config.get("reddit_api_key", os.environ.get("REDDIT_API_KEY", ""))
        
        # Tracking parameters
        self.update_interval = self.config.get("update_interval", 900)  # 15 minutes
        self.min_market_cap = self.config.get("min_market_cap", 100000)  # $100K
        self.max_tracked_coins = self.config.get("max_tracked_coins", 100)
        self.sentiment_threshold = self.config.get("sentiment_threshold", 0.7)  # 0-1 scale
        
        # Meme keyword patterns
        self.meme_patterns = self.config.get("meme_patterns", [
            r"dog(e|coin)", r"shib(a|)", r"cat", r"moon", r"safe", r"elon", r"mars", 
            r"cum", r"rocket", r"pepe", r"wojak", r"chad", r"baby", r"inu", r"floki"
        ])
        
        # Internal state
        self.session = None
        self.meme_coins = {}  # Tracked meme coins
        self.social_metrics = {}  # Social media metrics for coins
        self.is_tracking = False
        self.tracking_task = None
        self.last_updated = None
        
        # Alert history
        self.alerts = []
        self.max_alerts = self.config.get("max_alerts", 100)
        
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
        """Initialize the MemeCoins component.
        
        Returns:
            bool: True if initialization was successful
        """
        logger.info("Initializing MemeCoins component")
        
        # Subscribe to relevant events
        if self.event_bus is not None:
            self.event_bus and self.event_bus.subscribe_sync("memecoins.tracking.start", self.on_tracking_start)
            self.event_bus and self.event_bus.subscribe_sync("memecoins.tracking.stop", self.on_tracking_stop)
            self.event_bus and self.event_bus.subscribe_sync("memecoins.config.update", self.on_config_update)
            self.event_bus and self.event_bus.subscribe_sync("memecoins.add", self.on_add_memecoin)
            self.event_bus and self.event_bus.subscribe_sync("market.data.update", self.on_market_data_update)
            self.event_bus and self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
        else:
            logger.warning("No event bus available, MemeCoins will operate with limited functionality")
        
        # Create HTTP session
        self.session = aiohttp.ClientSession()
        
        # Load saved meme coins
        await self.load_meme_coins()
        
        # Start tracking if auto-start is enabled
        auto_start = True
        if self.config is not None:
            auto_start = self.config.get("auto_start", True)
        if auto_start:
            await self.start_tracking()
        
        logger.info("MemeCoins component initialized")
        return True
        
    async def load_meme_coins(self):
        """Load saved meme coins from storage."""
        data_dir = "data"
        if self.config is not None:
            data_dir = self.config.get("data_dir", "data")
        coins_file = os.path.join(data_dir, "meme_coins.json")
        
        try:
            if os.path.exists(coins_file):
                with open(coins_file, 'r') as f:
                    self.meme_coins = json.load(f)
                logger.info(f"Loaded {len(self.meme_coins)} meme coins")
        except Exception as e:
            logger.error(f"Error loading meme coins: {str(e)}")
            self.meme_coins = {}
    
    async def save_meme_coins(self):
        """Save meme coins to storage."""
        coins_file = os.path.join(self.config.get("data_dir", "data"), "meme_coins.json")
        
        try:
            os.makedirs(os.path.dirname(coins_file), exist_ok=True)
            with open(coins_file, 'w') as f:
                json.dump(self.meme_coins, f, indent=2)
            logger.info(f"Saved {len(self.meme_coins)} meme coins")
        except Exception as e:
            logger.error(f"Error saving meme coins: {str(e)}")
    
    async def start_tracking(self):
        """Start tracking meme coins."""
        if self.is_tracking:
            logger.warning("Meme coin tracking is already active")
            return
        
        logger.info("Starting meme coin tracking")
        self.is_tracking = True
        
        # Start tracking task
        if self.tracking_task is None or self.tracking_task.done():
            self.tracking_task = asyncio.create_task(self.track_meme_coins_loop())
        
        # Publish tracking started event
        await self.safe_publish("memecoins.tracking.started", {
            "timestamp": datetime.now().isoformat(),
            "tracked_coins": len(self.meme_coins)
        })
    
    async def stop_tracking(self):
        """Stop tracking meme coins."""
        if not self.is_tracking:
            logger.warning("Meme coin tracking is not active")
            return
        
        logger.info("Stopping meme coin tracking")
        self.is_tracking = False
        
        # Cancel tracking task
        if self.tracking_task and not self.tracking_task.done():
            self.tracking_task.cancel()
            try:
                await self.tracking_task
            except asyncio.CancelledError:
                pass
            self.tracking_task = None
        
        # Publish tracking stopped event
        await self.safe_publish("memecoins.tracking.stopped", {
            "timestamp": datetime.now().isoformat()
        })
    
    async def track_meme_coins_loop(self):
        """Continuously track meme coins at the specified interval."""
        try:
            # Initial scan for new meme coins
            await self.scan_for_meme_coins()
            
            while self.is_tracking:
                # Update data for tracked coins
                await self.update_meme_coins()
                
                # Update social metrics
                await self.update_social_metrics()
                
                # Generate alerts
                await self.generate_alerts()
                
                # Periodically scan for new meme coins (every 4 cycles)
                if not self.last_updated or (datetime.now() - self.last_updated).total_seconds() > self.update_interval * 4:
                    await self.scan_for_meme_coins()
                
                # Wait for next update
                await asyncio.sleep(self.update_interval)
                
        except asyncio.CancelledError:
            logger.info("Meme coin tracking loop cancelled")
        except Exception as e:
            logger.error(f"Error in meme coin tracking loop: {str(e)}")
            self.is_tracking = False
            
            # Restart tracking if configured to auto-restart
            if self.config.get("auto_restart", True):
                await asyncio.sleep(60)  # Wait before restarting
                await self.start_tracking()
    
    async def scan_for_meme_coins(self):
        """Scan for new meme coins."""
        logger.info("Scanning for new meme coins")
        
        try:
            # Fetch top 250 coins by market cap
            async with self.session.get(
                f"{self.coingecko_api_url}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "per_page": 250,
                    "page": 1,
                    "order": "market_cap_desc"
                }
            ) as response:
                if response.status == 200:
                    coins = await response.json()
                    
                    # Filter for potential meme coins based on name/symbol patterns
                    for coin in coins:
                        coin_id = coin.get("id")
                        name = coin.get("name", "").lower()
                        symbol = coin.get("symbol", "").lower()
                        market_cap = coin.get("market_cap", 0)
                        
                        # Skip if already tracked or below minimum market cap
                        if coin_id in self.meme_coins or market_cap < self.min_market_cap:
                            continue
                        
                        # Check if name or symbol matches meme patterns
                        is_meme_coin = False
                        for pattern in self.meme_patterns:
                            if re.search(pattern, name) or re.search(pattern, symbol):
                                is_meme_coin = True
                                break
                        
                        if is_meme_coin:
                            # Add to tracked meme coins
                            self.meme_coins[coin_id] = {
                                "id": coin_id,
                                "name": coin.get("name"),
                                "symbol": coin.get("symbol"),
                                "image": coin.get("image"),
                                "current_price": coin.get("current_price", 0),
                                "market_cap": market_cap,
                                "market_cap_rank": coin.get("market_cap_rank"),
                                "total_volume": coin.get("total_volume", 0),
                                "price_change_24h": coin.get("price_change_percentage_24h", 0),
                                "ath": coin.get("ath", 0),
                                "ath_date": coin.get("ath_date"),
                                "discovered_at": datetime.now().isoformat(),
                                "is_meme_coin": True,
                                "meme_score": 0.5,  # Initial score
                                "social_score": 0,
                                "risk_score": 0.5  # Initial risk score
                            }
                            
                            logger.info(f"Discovered new meme coin: {coin.get('name')} ({coin.get('symbol')})")
                    
                    # Enforce maximum tracked coins limit
                    if len(self.meme_coins) > self.max_tracked_coins:
                        # Sort by market cap and keep only the top ones
                        sorted_coins = sorted(
                            self.meme_coins.items(),
                            key=lambda x: x[1].get("market_cap", 0),
                            reverse=True
                        )
                        self.meme_coins = dict(sorted_coins[:self.max_tracked_coins])
                    
                    # Save updated meme coins
                    await self.save_meme_coins()
                    
                    # Publish discovered coins
                    await self.safe_publish("memecoins.discovered", {
                        "count": len(self.meme_coins),
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    logger.error(f"Failed to scan for meme coins. Status: {response.status}")
        except Exception as e:
            logger.error(f"Error scanning for meme coins: {str(e)}")
    
    async def update_meme_coins(self):
        """Update data for tracked meme coins."""
        if not self.meme_coins:
            return
            
        logger.info(f"Updating data for {len(self.meme_coins)} meme coins")
        
        try:
            # Get IDs of tracked coins
            coin_ids = list(self.meme_coins.keys())
            
            # Split into chunks of 50 (API limitation)
            chunk_size = 50
            for i in range(0, len(coin_ids), chunk_size):
                chunk = coin_ids[i:i+chunk_size]
                
                # Fetch updated data
                async with self.session.get(
                    f"{self.coingecko_api_url}/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "ids": ",".join(chunk),
                        "per_page": chunk_size,
                        "page": 1
                    }
                ) as response:
                    if response.status == 200:
                        coins = await response.json()
                        
                        for coin in coins:
                            coin_id = coin.get("id")
                            if coin_id in self.meme_coins:
                                # Update coin data
                                self.meme_coins[coin_id].update({
                                    "current_price": coin.get("current_price", 0),
                                    "market_cap": coin.get("market_cap", 0),
                                    "market_cap_rank": coin.get("market_cap_rank"),
                                    "total_volume": coin.get("total_volume", 0),
                                    "price_change_24h": coin.get("price_change_percentage_24h", 0),
                                    "last_updated": datetime.now().isoformat()
                                })
                                
                                # Calculate volatility based on price change
                                price_change = abs(coin.get("price_change_percentage_24h", 0))
                                if price_change > 50:
                                    volatility = 1.0  # Extremely volatile
                                elif price_change > 30:
                                    volatility = 0.8
                                elif price_change > 20:
                                    volatility = 0.6
                                elif price_change > 10:
                                    volatility = 0.4
                                else:
                                    volatility = 0.2
                                
                                self.meme_coins[coin_id]["volatility"] = volatility
                                
                                # Calculate volume/market cap ratio (liquidity indicator)
                                market_cap = coin.get("market_cap", 0)
                                if market_cap > 0:
                                    volume_market_cap_ratio = coin.get("total_volume", 0) / market_cap
                                    self.meme_coins[coin_id]["volume_market_cap_ratio"] = volume_market_cap_ratio
                                else:
                                    self.meme_coins[coin_id]["volume_market_cap_ratio"] = 0
                    else:
                        logger.error(f"Failed to update meme coins. Status: {response.status}")
            
            # Save updated meme coins
            await self.save_meme_coins()
            
            # Update last updated timestamp
            self.last_updated = datetime.now()
            
            # Publish updated data
            await self.safe_publish("memecoins.updated", {
                "count": len(self.meme_coins),
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error updating meme coins: {str(e)}")
    
    async def update_social_metrics(self):
        """Update social media metrics for tracked coins."""
        # This would typically integrate with Twitter, Reddit, and other social APIs
        # For this example, we'll simulate social metrics
        
        for coin_id, coin_data in self.meme_coins.items():
            try:
                name = coin_data.get("name", "")
                symbol = coin_data.get("symbol", "")
                
                # Simulate social metrics
                mentions = hash(f"{name}_{datetime.now().hour}") % 1000
                sentiment = (hash(f"{symbol}_{datetime.now().day}") % 100) / 100.0
                trending_score = (hash(f"{name}_{datetime.now().day}_{datetime.now().hour}") % 100) / 100.0
                
                social_data = {
                    "mentions": mentions,
                    "sentiment": sentiment,
                    "trending_score": trending_score,
                    "last_updated": datetime.now().isoformat()
                }
                
                # Store social metrics
                self.social_metrics[coin_id] = social_data
                
                # Update coin with social score
                self.meme_coins[coin_id]["social_score"] = trending_score
                
                # Calculate overall meme score (combination of volatility, social trending, etc.)
                volatility = self.meme_coins[coin_id].get("volatility", 0.5)
                volume_market_cap_ratio = self.meme_coins[coin_id].get("volume_market_cap_ratio", 0)
                
                # Higher volume/market cap ratio indicates higher liquidity (good)
                liquidity_score = min(1.0, volume_market_cap_ratio * 5)
                
                # Calculate meme score: 40% trending, 30% volatility, 30% liquidity
                meme_score = (trending_score * 0.4) + (volatility * 0.3) + (liquidity_score * 0.3)
                self.meme_coins[coin_id]["meme_score"] = meme_score
                
                # Calculate risk score: higher volatility and lower liquidity = higher risk
                risk_score = (volatility * 0.7) + ((1 - liquidity_score) * 0.3)
                self.meme_coins[coin_id]["risk_score"] = risk_score
                
            except Exception as e:
                logger.error(f"Error updating social metrics for {coin_id}: {str(e)}")
        
        logger.info(f"Updated social metrics for {len(self.social_metrics)} meme coins")
    
    async def generate_alerts(self):
        """Generate alerts for significant meme coin events."""
        for coin_id, coin_data in self.meme_coins.items():
            try:
                # Check for price pumps
                price_change = coin_data.get("price_change_24h", 0)
                if price_change > 30:  # 30% pump
                    await self.create_alert(
                        coin_id,
                        "price_pump",
                        f"{coin_data.get('name')} ({coin_data.get('symbol')}) pumped {price_change:.1f}% in 24h",
                        {"price_change": price_change}
                    )
                
                # Check for trending coins
                social_score = coin_data.get("social_score", 0)
                if social_score > self.sentiment_threshold:
                    await self.create_alert(
                        coin_id,
                        "trending",
                        f"{coin_data.get('name')} ({coin_data.get('symbol')}) is trending on social media",
                        {"social_score": social_score}
                    )
                
                # Check for high meme score coins
                meme_score = coin_data.get("meme_score", 0)
                if meme_score > 0.8:  # Very high meme potential
                    await self.create_alert(
                        coin_id,
                        "high_meme_potential",
                        f"{coin_data.get('name')} ({coin_data.get('symbol')}) has high meme potential",
                        {"meme_score": meme_score}
                    )
                
                # Check for high risk coins
                risk_score = coin_data.get("risk_score", 0)
                if risk_score > 0.8:  # Very high risk
                    await self.create_alert(
                        coin_id,
                        "high_risk",
                        f"{coin_data.get('name')} ({coin_data.get('symbol')}) has high risk profile",
                        {"risk_score": risk_score}
                    )
                
            except Exception as e:
                logger.error(f"Error generating alerts for {coin_id}: {str(e)}")
    
    async def create_alert(self, coin_id, alert_type, message, data=None):
        """
        Create a new meme coin alert.
        
        Args:
            coin_id: ID of the coin
            alert_type: Type of alert
            message: Alert message
            data: Additional alert data
        """
        # Check if similar alert already exists in the last 24 hours
        cutoff_time = datetime.now() - timedelta(hours=24)
        for alert in self.alerts:
            if (alert.get("coin_id") == coin_id and 
                alert.get("type") == alert_type and 
                datetime.fromisoformat(alert.get("timestamp")) > cutoff_time):
                return  # Skip duplicate alert
        
        # Create alert
        alert = {
            "id": f"{coin_id}_{alert_type}_{int(datetime.now().timestamp())}",
            "coin_id": coin_id,
            "type": alert_type,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to alerts history
        self.alerts.append(alert)
        
        # Limit alerts history size
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]
        
        # Publish alert
        await self.safe_publish("memecoins.alert", alert)
        
        logger.info(f"Meme coin alert: {message}")
    
    async def add_custom_memecoin(self, data):
        """
        Add a custom meme coin to track.
        
        Args:
            data: Coin data including id, name, symbol
            
        Returns:
            bool: Success status
        """
        coin_id = data.get("id")
        if not coin_id:
            logger.error("Cannot add meme coin: missing id")
            return False
        
        if coin_id in self.meme_coins:
            logger.warning(f"Meme coin {coin_id} is already being tracked")
            return False
        
        # Add basic coin information
        self.meme_coins[coin_id] = {
            "id": coin_id,
            "name": data.get("name", coin_id),
            "symbol": data.get("symbol", ""),
            "is_custom": True,
            "discovered_at": datetime.now().isoformat(),
            "is_meme_coin": True,
            "meme_score": 0.5,  # Initial score
            "social_score": 0,
            "risk_score": 0.5,  # Initial risk score
            "market_cap": 0,
            "current_price": 0
        }
        
        # Save updated meme coins
        await self.save_meme_coins()
        
        logger.info(f"Added custom meme coin: {data.get('name')} ({data.get('symbol')})")
        return True
    
    async def get_top_meme_coins(self, limit=10, sort_by="meme_score"):
        """
        Get top meme coins by specified criteria.
        
        Args:
            limit: Maximum number of coins to return
            sort_by: Criteria to sort by (meme_score, market_cap, price_change_24h)
            
        Returns:
            list: Top meme coins
        """
        if not self.meme_coins:
            return []
        
        # Determine sort key
        if sort_by == "meme_score":
            sort_key = lambda x: x[1].get("meme_score", 0)
        elif sort_by == "market_cap":
            sort_key = lambda x: x[1].get("market_cap", 0)
        elif sort_by == "price_change_24h":
            sort_key = lambda x: x[1].get("price_change_24h", 0)
        else:
            sort_key = lambda x: x[1].get("meme_score", 0)
        
        # Sort coins
        sorted_coins = sorted(
            self.meme_coins.items(),
            key=sort_key,
            reverse=True
        )
        
        # Return top coins
        return [coin[1] for coin in sorted_coins[:limit]]
    
    async def get_recent_alerts(self, limit=10, alert_type=None):
        """
        Get recent meme coin alerts.
        
        Args:
            limit: Maximum number of alerts to return
            alert_type: Filter by alert type
            
        Returns:
            list: Recent alerts
        """
        # Filter by type if specified
        if alert_type:
            filtered_alerts = [alert for alert in self.alerts if alert.get("type") == alert_type]
        else:
            filtered_alerts = self.alerts
        
        # Sort by timestamp (newest first)
        sorted_alerts = sorted(
            filtered_alerts,
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
        
        # Return recent alerts
        return sorted_alerts[:limit]
    
    async def on_tracking_start(self, _):
        """Handle tracking start event."""
        await self.start_tracking()
    
    async def on_tracking_stop(self, _):
        """Handle tracking stop event."""
        await self.stop_tracking()
    
    async def on_config_update(self, data):
        """
        Handle config update event.
        
        Args:
            data: New configuration data
        """
        config = data.get("config", {})
        
        # Update configuration
        if "update_interval" in config:
            self.update_interval = config["update_interval"]
            
        if "min_market_cap" in config:
            self.min_market_cap = config["min_market_cap"]
            
        if "max_tracked_coins" in config:
            self.max_tracked_coins = config["max_tracked_coins"]
            
        if "sentiment_threshold" in config:
            self.sentiment_threshold = config["sentiment_threshold"]
            
        if "meme_patterns" in config:
            self.meme_patterns = config["meme_patterns"]
        
        # Restart tracking if running
        was_tracking = self.is_tracking
        if was_tracking:
            await self.stop_tracking()
            await self.start_tracking()
        
        logger.info("Updated meme coins configuration")
        
        # Publish config update result
        await self.safe_publish("memecoins.config.updated", {
            "request_id": data.get("request_id"),
            "config": {
                "update_interval": self.update_interval,
                "min_market_cap": self.min_market_cap,
                "max_tracked_coins": self.max_tracked_coins,
                "sentiment_threshold": self.sentiment_threshold,
                "meme_patterns": self.meme_patterns
            },
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_add_memecoin(self, data):
        """
        Handle add memecoin event.
        
        Args:
            data: Coin data
        """
        success = await self.add_custom_memecoin(data)
        
        # Publish result
        await self.safe_publish("memecoins.add.result", {
            "request_id": data.get("request_id"),
            "success": success,
            "coin_id": data.get("id"),
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_market_data_update(self, data):
        """
        Handle market data update event.
        
        Args:
            data: Market data update
        """
        try:
            if not isinstance(data, dict):
                return

            symbol = data.get("symbol", "").lower()
            price = data.get("price")
            volume_24h = data.get("volume_24h")
            market_cap = data.get("market_cap")

            if not symbol:
                return

            for coin_id, coin_data in self.tracked_coins.items():
                if coin_data.get("symbol", "").lower() == symbol or coin_id == symbol:
                    if price is not None:
                        coin_data["current_price"] = float(price)
                    if volume_24h is not None:
                        coin_data["volume_24h"] = float(volume_24h)
                    if market_cap is not None:
                        coin_data["market_cap"] = float(market_cap)
                    coin_data["last_updated"] = datetime.now().isoformat()
                    logger.debug("Updated market data for meme coin: %s", coin_id)
                    break
        except Exception as e:
            logger.error("Error processing market data update: %s", e)
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the MemeCoins component."""
        logger.info("Shutting down MemeCoins component")
        
        # Stop tracking
        if self.is_tracking:
            await self.stop_tracking()
        
        # Save data
        await self.save_meme_coins()
        
        # Close HTTP session
        if self.session:
            await self.session.close()
        
        logger.info("MemeCoins component shut down successfully")
