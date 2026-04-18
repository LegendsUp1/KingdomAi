#!/usr/bin/env python3
"""
Strategy Marketplace for Kingdom AI

This module provides a marketplace for trading strategies where users can discover,
share, rate, and subscribe to trading strategies.
"""

import logging
import json
import os
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from core.base_component import BaseComponent
from core.strategy_marketplace_handlers import StrategyMarketplaceHandlers
from core.strategy_marketplace_ai import StrategyMarketplaceAI

class StrategyMarketplace(BaseComponent, StrategyMarketplaceHandlers, StrategyMarketplaceAI):
    """
    Strategy Marketplace component for the Kingdom AI system.
    
    This component manages the discovery, sharing, rating, and subscription
    of trading strategies within the Kingdom AI ecosystem.
    """
    
    def __init__(self, event_bus=None, config=None, 
                 trading_system=None, thoth_ai=None, copy_trading=None):
        """
        Initialize the Strategy Marketplace component.
        
        Args:
            event_bus: Event bus for inter-component communication
            config: Configuration settings for the marketplace
            trading_system: Reference to the Trading System component
            thoth_ai: Reference to the ThothAI component
            copy_trading: Reference to the Copy Trading component
        """
        super().__init__(event_bus=event_bus, config=config or {})
        self.name = "StrategyMarketplace"
        self.description = "Marketplace for trading strategies"
        self.logger = logging.getLogger("KingdomAI.StrategyMarketplace")
        
        # Component connections
        self.trading_system = trading_system
        self.thoth_ai = thoth_ai
        self.copy_trading = copy_trading
        
        # Configuration
        self.config_file = self.config.get("config_file", "configs/strategy_marketplace_config.json")
        self.marketplace_config = self._load_config()
        
        # Strategy storage
        self.strategies_file = self.marketplace_config.get("strategies_file", "data/strategies.json")
        self.strategies = {}
        self.featured_strategies = []
        
        # User subscriptions
        self.user_subscriptions = {}
        
        # Ratings and reviews
        self.ratings = {}
        self.reviews = {}
        
        # Statistics
        self.download_stats = {}
        self.performance_stats = {}
        
        # Initialization state
        self._initialized = False
        self._snapshot_interval = float(self.marketplace_config.get("snapshot_interval_seconds", 30.0))
        
        self.logger.info(f"{self.name} created")

    def _emit_trading_telemetry(
        self,
        event_type: str,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Best-effort trading telemetry emitter for marketplace events.

        Publishes lightweight payloads on trading.telemetry without raising
        on failure. This must never interfere with core marketplace logic.
        """
        try:
            if not getattr(self, "event_bus", None):
                return
            payload: Dict[str, Any] = {
                "component": "trading",
                "channel": "trading.telemetry",
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "success": success,
                "error": error,
                "metadata": metadata or {},
            }
            self.event_bus.publish("trading.telemetry", payload)
        except Exception as e:  # pragma: no cover - telemetry must never break flows
            self.logger.debug("StrategyMarketplace telemetry publish failed for %s: %s", event_type, e)

    def _load_config(self) -> Dict[str, Any]:
        """
        Load marketplace configuration from file or use defaults.
        
        Returns:
            Dict[str, Any]: Marketplace configuration settings
        """
        default_config = {
            "strategies_file": "data/strategies.json",
            "max_featured_strategies": 10,
            "auto_approve_strategies": False,
            "require_backtesting": True,
            "min_backtesting_days": 30,
            "allow_ai_optimized_strategies": True,
            "max_strategy_size_kb": 500,
            "categories": [
                "Trend Following", "Mean Reversion", "Momentum", 
                "Breakout", "Statistical Arbitrage", "AI/ML", 
                "Algorithmic", "Sentiment Based", "Market Neutral",
                "Pairs Trading", "Volatility / Options", "Range / Sideways",
                "Event Driven / Volatility", "Reinforcement Learning",
                "DeFi / Blockchain", "Alternative Data / AI",
            ],
            "supported_markets": [
                "Cryptocurrency", "Forex", "Stocks", "Options", 
                "Futures", "Commodities", "Indices"
            ],
            "risk_levels": ["Low", "Medium", "High", "Very High"],
            "rating_categories": [
                "Overall Performance", "Risk Management", 
                "Documentation", "Code Quality", "Innovation"
            ]
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    self.logger.info(f"Loaded configuration from {self.config_file}")
                    # Merge with defaults to ensure all keys exist
                    for key, value in default_config.items():
                        if key not in loaded_config:
                            loaded_config[key] = value
                    return loaded_config
        except Exception as e:
            self.logger.error(f"Error loading config from {self.config_file}: {e}")
        
        # Create config directory and file if it doesn't exist
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
                self.logger.info(f"Created default configuration at {self.config_file}")
        except Exception as e:
            self.logger.error(f"Error creating default config at {self.config_file}: {e}")
        
        return default_config
    
    async def initialize(self) -> bool:
        """
        Initialize the Strategy Marketplace component.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            self.logger.info("Initializing Strategy Marketplace...")
            
            # Load strategies
            await self._load_strategies()
            
            # Subscribe to events
            if self.event_bus:
                # Strategy management events
                await self.subscribe_to_event("strategy.submit", self._handle_strategy_submit)
                await self.subscribe_to_event("strategy.update", self._handle_strategy_update)
                await self.subscribe_to_event("strategy.delete", self._handle_strategy_delete)
                await self.subscribe_to_event("strategy.rate", self._handle_strategy_rate)
                await self.subscribe_to_event("strategy.review", self._handle_strategy_review)
                
                # Strategy discovery events
                await self.subscribe_to_event("strategy.search", self._handle_strategy_search)
                await self.subscribe_to_event("strategy.browse", self._handle_strategy_browse)
                await self.subscribe_to_event("strategy.get_details", self._handle_strategy_get_details)
                
                # Strategy subscription events
                await self.subscribe_to_event("strategy.subscribe", self._handle_strategy_subscribe)
                await self.subscribe_to_event("strategy.unsubscribe", self._handle_strategy_unsubscribe)
                
                # AI integration events
                await self.subscribe_to_event("strategy.generate", self._handle_strategy_generate)
                await self.subscribe_to_event("strategy.optimize", self._handle_strategy_optimize)
                await self.subscribe_to_event("strategy.analyze", self._handle_strategy_analyze)
                
                # System events
                await self.subscribe_to_event("system.shutdown", self._handle_shutdown)
                
                self.logger.info("Subscribed to strategy marketplace events")
            
            # Publish initialization status
            await self.publish_event("component.status", {
                "component": "strategy_marketplace",
                "status": "ready",
                "message": "Strategy Marketplace initialized and ready"
            })
            
            self._initialized = True
            self.logger.info("Strategy Marketplace initialized successfully")

            # Telemetry: marketplace initialized
            self._emit_trading_telemetry(
                event_type="strategy_marketplace.initialize",
                success=True,
                metadata={
                    "strategy_count": len(self.strategies),
                    "snapshot_interval": self._snapshot_interval,
                },
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing Strategy Marketplace: {e}")
            self._emit_trading_telemetry(
                event_type="strategy_marketplace.initialize",
                success=False,
                error=str(e),
            )
            return False
    
    async def _load_strategies(self) -> None:
        """Load strategies from storage."""
        try:
            if os.path.exists(self.strategies_file):
                with open(self.strategies_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.strategies = data.get("strategies", {})
                    self.ratings = data.get("ratings", {})
                    self.reviews = data.get("reviews", {})
                    self.download_stats = data.get("downloads", {})
                    self.performance_stats = data.get("performance", {})
                    self.user_subscriptions = data.get("subscriptions", {})
                    
                    self.logger.info(f"Loaded {len(self.strategies)} strategies from {self.strategies_file}")
                    
                    # Update featured strategies
                    await self._update_featured_strategies()
            else:
                self.logger.info(f"No strategies file found at {self.strategies_file}, starting with empty marketplace")
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(self.strategies_file), exist_ok=True)
        except Exception as e:
            self.logger.error(f"Error loading strategies: {e}")
    
    async def _save_strategies(self) -> None:
        """Save strategies to storage."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.strategies_file), exist_ok=True)
            
            with open(self.strategies_file, 'w', encoding='utf-8') as f:
                data = {
                    "strategies": self.strategies,
                    "ratings": self.ratings,
                    "reviews": self.reviews,
                    "downloads": self.download_stats,
                    "performance": self.performance_stats,
                    "subscriptions": self.user_subscriptions
                }
                json.dump(data, f, indent=2)
                
            self.logger.info(f"Saved {len(self.strategies)} strategies to {self.strategies_file}")
        except Exception as e:
            self.logger.error(f"Error saving strategies: {e}")
    
    async def _update_featured_strategies(self) -> None:
        """Update the list of featured strategies based on ratings and popularity."""
        try:
            # Sort strategies by rating and popularity
            sorted_strategies = []
            
            for strategy_id, strategy in self.strategies.items():
                # Skip strategies that are not approved
                if not strategy.get("approved", False):
                    continue
                
                # Calculate average rating
                avg_rating = 0.0
                if strategy_id in self.ratings:
                    ratings = self.ratings[strategy_id]
                    if ratings:
                        avg_rating = sum(r["rating"] for r in ratings.values()) / len(ratings)
                
                # Get download count
                downloads = self.download_stats.get(strategy_id, {}).get("count", 0)
                
                # Calculate score based on rating and downloads
                score = (avg_rating * 0.7) + (min(downloads / 100, 5) * 0.3)
                
                sorted_strategies.append((strategy_id, score))
            
            # Sort by score in descending order
            sorted_strategies.sort(key=lambda x: x[1], reverse=True)
            
            # Get top N strategies
            max_featured = self.marketplace_config.get("max_featured_strategies", 10)
            self.featured_strategies = [s[0] for s in sorted_strategies[:max_featured]]
            
            self.logger.info(f"Updated featured strategies: {len(self.featured_strategies)} strategies selected")
        except Exception as e:
            self.logger.error(f"Error updating featured strategies: {e}")

    async def _snapshot_loop(self) -> None:
        """Periodically publish a lightweight marketplace snapshot for dashboards."""
        try:
            interval_cfg = self.marketplace_config.get("snapshot_interval_seconds", self._snapshot_interval)
            try:
                interval = float(interval_cfg)
            except (TypeError, ValueError):
                interval = 30.0
            if interval <= 0:
                interval = 30.0

            while True:
                try:
                    await self._publish_marketplace_snapshot()
                except Exception as e:
                    self.logger.error(f"Error in strategy marketplace snapshot loop: {e}")
                await asyncio.sleep(interval)
        except Exception as e:
            self.logger.error(f"Failed to start strategy marketplace snapshot loop: {e}")

    async def _publish_marketplace_snapshot(self) -> None:
        """Publish a concise strategy marketplace snapshot on the event bus."""
        if not self.event_bus:
            return
        try:
            payload = self._build_marketplace_snapshot_payload()
            await self.publish_event("trading.strategy_marketplace.snapshot", payload)

            # Telemetry: snapshot published
            try:
                self._emit_trading_telemetry(
                    event_type="strategy_marketplace.snapshot_published",
                    success=True,
                    metadata={
                        "strategy_count": payload.get("strategy_count", 0),
                        "featured_count": len(payload.get("featured_strategy_ids", [])),
                        "total_subscriptions": payload.get("summary", {}).get("total_subscriptions", 0),
                    },
                )
            except Exception:
                self.logger.debug("Telemetry error in _publish_marketplace_snapshot", exc_info=True)
        except Exception as e:
            self.logger.error(f"Error publishing strategy marketplace snapshot: {e}")
            self._emit_trading_telemetry(
                event_type="strategy_marketplace.snapshot_error",
                success=False,
                error=str(e),
            )

    def _build_marketplace_snapshot_payload(self) -> Dict[str, Any]:
        """Build a lightweight snapshot payload for dashboards."""
        timestamp = datetime.now().timestamp()

        # Aggregate global statistics
        total_subscriptions = 0
        try:
            for subs in self.user_subscriptions.values():
                if isinstance(subs, list):
                    total_subscriptions += len(subs)
        except Exception:
            total_subscriptions = 0

        total_ratings = 0
        for ratings in self.ratings.values():
            if isinstance(ratings, dict):
                total_ratings += len(ratings)

        total_reviews = 0
        for reviews in self.reviews.values():
            if isinstance(reviews, dict):
                total_reviews += len(reviews)

        strategy_summaries = []

        for strategy_id, strategy in self.strategies.items():
            if not isinstance(strategy, dict):
                continue

            name = str(strategy.get("name") or "")
            category = str(strategy.get("category") or "")
            risk_level = str(strategy.get("risk_level") or "")

            # Average rating per strategy
            avg_rating = 0.0
            ratings_dict = self.ratings.get(strategy_id)
            if isinstance(ratings_dict, dict) and ratings_dict:
                total_score = 0.0
                count = 0
                for rating_entry in ratings_dict.values():
                    if not isinstance(rating_entry, dict):
                        continue
                    rating_val = rating_entry.get("rating")
                    if isinstance(rating_val, (int, float)):
                        total_score += float(rating_val)
                        count += 1
                if count:
                    avg_rating = total_score / count

            # Subscription count per strategy
            subscribers = 0
            try:
                for subs in self.user_subscriptions.values():
                    if isinstance(subs, list) and strategy_id in subs:
                        subscribers += 1
            except Exception:
                subscribers = 0

            perf = self.performance_stats.get(strategy_id, {}) or {}
            win_rate = perf.get("win_rate")
            profit_factor = perf.get("profit_factor")
            sharpe_ratio = perf.get("sharpe_ratio")
            max_drawdown = perf.get("max_drawdown")

            summary: Dict[str, Any] = {
                "id": strategy_id,
                "name": name,
                "category": category,
                "risk_level": risk_level,
                "avg_rating": float(avg_rating),
                "subscribers": int(subscribers),
            }

            if isinstance(win_rate, (int, float)):
                summary["win_rate"] = float(win_rate)
            if isinstance(profit_factor, (int, float)):
                summary["profit_factor"] = float(profit_factor)
            if isinstance(sharpe_ratio, (int, float)):
                summary["sharpe_ratio"] = float(sharpe_ratio)
            if isinstance(max_drawdown, (int, float)):
                summary["max_drawdown"] = float(max_drawdown)

            strategy_summaries.append(summary)

        # Sort to surface most interesting strategies
        def _sort_key(item: Dict[str, Any]) -> float:
            rating_val = item.get("avg_rating") or 0.0
            win_rate_val = item.get("win_rate") or 0.0
            try:
                return float(rating_val) * 2.0 + float(win_rate_val)
            except Exception:
                return 0.0

        strategy_summaries.sort(key=_sort_key, reverse=True)

        payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "strategy_count": len(self.strategies),
            "featured_strategy_ids": list(self.featured_strategies),
            "summary": {
                "total_subscriptions": int(total_subscriptions),
                "total_ratings": int(total_ratings),
                "total_reviews": int(total_reviews),
            },
            # Limit to top 50 strategies to keep payload compact
            "strategies": strategy_summaries[:50],
        }

        return payload
    
    # Event handlers for strategy management
    
    async def _handle_strategy_submit(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy submission event.
        
        Args:
            data: Strategy submission data including code, metadata, etc.
        """
        try:
            if not data or "strategy" not in data:
                await self._publish_error("submit", "No strategy data provided")
                return
            
            strategy_data = data["strategy"]
            
            # Validate required fields
            required_fields = ["name", "description", "code", "author", "category", "risk_level"]
            missing_fields = [field for field in required_fields if field not in strategy_data]
            
            if missing_fields:
                await self._publish_error("submit", f"Missing required fields: {', '.join(missing_fields)}")
                return
            
            # Generate unique ID for the strategy
            strategy_id = str(uuid.uuid4())
            
            # Add system fields
            strategy_data["id"] = strategy_id
            strategy_data["created_at"] = datetime.now().isoformat()
            strategy_data["updated_at"] = datetime.now().isoformat()
            strategy_data["approved"] = self.marketplace_config.get("auto_approve_strategies", False)
            strategy_data["version"] = "1.0.0"
            
            # Store the strategy
            self.strategies[strategy_id] = strategy_data
            
            # Initialize statistics
            self.download_stats[strategy_id] = {"count": 0, "users": []}
            self.performance_stats[strategy_id] = {
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "total_trades": 0,
                "profitable_trades": 0,
                "last_updated": datetime.now().isoformat()
            }
            
            # Save strategies
            await self._save_strategies()
            
            # Update featured strategies if this one is approved
            if strategy_data["approved"]:
                await self._update_featured_strategies()
            
            # Publish strategy submitted event
            if self.event_bus:
                await self.publish_event("strategy.submitted", {
                    "strategy_id": strategy_id,
                    "name": strategy_data["name"],
                    "author": strategy_data["author"],
                    "needs_approval": not strategy_data["approved"],
                    "timestamp": datetime.now().isoformat()
                })
            
            self.logger.info(f"Strategy submitted: {strategy_data['name']} by {strategy_data['author']} (ID: {strategy_id})")
            
        except Exception as e:
            self.logger.error(f"Error handling strategy submission: {e}")
            await self._publish_error("submit", str(e))
    
    async def _handle_strategy_update(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy update event.
        
        Args:
            data: Strategy update data including ID and updated fields
        """
        try:
            if not data or "strategy_id" not in data or "updates" not in data:
                await self._publish_error("update", "Missing strategy_id or updates in request")
                return
            
            strategy_id = data["strategy_id"]
            updates = data["updates"]
            
            # Check if strategy exists
            if strategy_id not in self.strategies:
                await self._publish_error("update", f"Strategy with ID {strategy_id} not found")
                return
            
            # Get the strategy
            strategy = self.strategies[strategy_id]
            
            # Update fields
            for key, value in updates.items():
                # Don't allow updating certain fields
                if key in ["id", "created_at", "author"]:
                    continue
                
                strategy[key] = value
            
            # Update timestamp
            strategy["updated_at"] = datetime.now().isoformat()
            
            # Increment version if code was updated
            if "code" in updates:
                version_parts = strategy["version"].split(".")
                version_parts[-1] = str(int(version_parts[-1]) + 1)
                strategy["version"] = ".".join(version_parts)
            
            # Save strategies
            await self._save_strategies()
            
            # Update featured strategies
            await self._update_featured_strategies()
            
            # Publish strategy updated event
            if self.event_bus:
                await self.publish_event("strategy.updated", {
                    "strategy_id": strategy_id,
                    "name": strategy["name"],
                    "version": strategy["version"],
                    "timestamp": datetime.now().isoformat()
                })
            
            self.logger.info(f"Strategy updated: {strategy['name']} (ID: {strategy_id}) to version {strategy['version']}")
            
        except Exception as e:
            self.logger.error(f"Error handling strategy update: {e}")
            await self._publish_error("update", str(e))
    
    async def _handle_strategy_delete(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy deletion event.
        
        Args:
            data: Strategy deletion data including ID
        """
        try:
            if not data or "strategy_id" not in data:
                await self._publish_error("delete", "Missing strategy_id in request")
                return
            
            strategy_id = data["strategy_id"]
            
            # Check if strategy exists
            if strategy_id not in self.strategies:
                await self._publish_error("delete", f"Strategy with ID {strategy_id} not found")
                return
            
            # Get strategy name for logging
            strategy_name = self.strategies[strategy_id]["name"]
            
            # Remove the strategy
            del self.strategies[strategy_id]
            
            # Remove related data
            if strategy_id in self.ratings:
                del self.ratings[strategy_id]
            
            if strategy_id in self.reviews:
                del self.reviews[strategy_id]
            
            if strategy_id in self.download_stats:
                del self.download_stats[strategy_id]
            
            if strategy_id in self.performance_stats:
                del self.performance_stats[strategy_id]
            
            # Remove from subscriptions
            for user_id, subscriptions in self.user_subscriptions.items():
                if strategy_id in subscriptions:
                    subscriptions.remove(strategy_id)
            
            # Save strategies
            await self._save_strategies()
            
            # Update featured strategies
            await self._update_featured_strategies()
            
            # Publish strategy deleted event
            if self.event_bus:
                await self.publish_event("strategy.deleted", {
                    "strategy_id": strategy_id,
                    "name": strategy_name,
                    "timestamp": datetime.now().isoformat()
                })
            
            self.logger.info(f"Strategy deleted: {strategy_name} (ID: {strategy_id})")
            
        except Exception as e:
            self.logger.error(f"Error handling strategy deletion: {e}")
            await self._publish_error("delete", str(e))
            
    async def _handle_shutdown(self, event_data: Dict[str, Any]) -> None:
        try:
            self.logger.info("StrategyMarketplace received system shutdown event: %s", event_data)
            await self.stop()
        except Exception as e:
            self.logger.error(f"Error handling StrategyMarketplace shutdown: {e}")
