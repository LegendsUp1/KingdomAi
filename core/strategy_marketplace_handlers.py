#!/usr/bin/env python3
"""
Strategy Marketplace Event Handlers for Kingdom AI

This module provides the event handlers for the Strategy Marketplace component,
handling strategy rating, review, search, browse, and subscription events.
"""

import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger("KingdomAI.StrategyMarketplace")

class StrategyMarketplaceHandlers:
    """Handler methods for the Strategy Marketplace component."""
    
    # Rating and review handlers
    
    async def _handle_strategy_rate(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy rating event.
        
        Args:
            data: Strategy rating data including ID, user ID, and rating
        """
        try:
            if not data or "strategy_id" not in data or "user_id" not in data or "rating" not in data:
                await self._publish_error("rate", "Missing required fields in rating request")
                return
            
            strategy_id = data["strategy_id"]
            user_id = data["user_id"]
            rating_value = data["rating"]
            
            # Validate rating value
            if not isinstance(rating_value, (int, float)) or rating_value < 1 or rating_value > 5:
                await self._publish_error("rate", "Rating must be a number between 1 and 5")
                return
            
            # Check if strategy exists
            if strategy_id not in self.strategies:
                await self._publish_error("rate", f"Strategy with ID {strategy_id} not found")
                return
            
            # Initialize ratings for this strategy if needed
            if strategy_id not in self.ratings:
                self.ratings[strategy_id] = {}
            
            # Add or update rating
            self.ratings[strategy_id][user_id] = {
                "rating": rating_value,
                "timestamp": datetime.now().isoformat()
            }
            
            # Calculate new average rating
            avg_rating = sum(r["rating"] for r in self.ratings[strategy_id].values()) / len(self.ratings[strategy_id])
            
            # Save strategies
            await self._save_strategies()
            
            # Update featured strategies
            await self._update_featured_strategies()
            
            # Publish rating update event
            if self.event_bus:
                await self.publish_event("strategy.rated", {
                    "strategy_id": strategy_id,
                    "name": self.strategies[strategy_id]["name"],
                    "user_id": user_id,
                    "rating": rating_value,
                    "avg_rating": avg_rating,
                    "total_ratings": len(self.ratings[strategy_id]),
                    "timestamp": datetime.now().isoformat()
                })
            
            self.logger.info(f"Strategy rated: {self.strategies[strategy_id]['name']} (ID: {strategy_id}) - {rating_value}/5 by user {user_id}")

            # Telemetry: rating success
            try:
                if hasattr(self, "_emit_trading_telemetry"):
                    self._emit_trading_telemetry(
                        event_type="strategy_marketplace.rate",
                        success=True,
                        metadata={
                            "strategy_id": strategy_id,
                            "user_id": user_id,
                            "rating": rating_value,
                            "avg_rating": avg_rating,
                        },
                    )
            except Exception:
                logger.debug("Telemetry error in _handle_strategy_rate", exc_info=True)
            
        except Exception as e:
            self.logger.error(f"Error handling strategy rating: {e}")
            await self._publish_error("rate", str(e))
    
    async def _handle_strategy_review(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy review event.
        
        Args:
            data: Strategy review data including ID, user ID, and review text
        """
        try:
            if not data or "strategy_id" not in data or "user_id" not in data or "review" not in data:
                await self._publish_error("review", "Missing required fields in review request")
                return
            
            strategy_id = data["strategy_id"]
            user_id = data["user_id"]
            review_text = data["review"]
            
            # Check if strategy exists
            if strategy_id not in self.strategies:
                await self._publish_error("review", f"Strategy with ID {strategy_id} not found")
                return
            
            # Initialize reviews for this strategy if needed
            if strategy_id not in self.reviews:
                self.reviews[strategy_id] = {}
            
            # Add or update review
            self.reviews[strategy_id][user_id] = {
                "text": review_text,
                "timestamp": datetime.now().isoformat()
            }
            
            # Save strategies
            await self._save_strategies()
            
            # Publish review update event
            if self.event_bus:
                await self.publish_event("strategy.reviewed", {
                    "strategy_id": strategy_id,
                    "name": self.strategies[strategy_id]["name"],
                    "user_id": user_id,
                    "review": review_text,
                    "timestamp": datetime.now().isoformat()
                })
            
            self.logger.info(f"Strategy reviewed: {self.strategies[strategy_id]['name']} (ID: {strategy_id}) by user {user_id}")
            try:
                if hasattr(self, "_emit_trading_telemetry"):
                    self._emit_trading_telemetry(
                        event_type="strategy_marketplace.review",
                        success=True,
                        metadata={
                            "strategy_id": strategy_id,
                            "user_id": user_id,
                        },
                    )
            except Exception:
                logger.debug("Telemetry error in _handle_strategy_review", exc_info=True)
            
        except Exception as e:
            self.logger.error(f"Error handling strategy review: {e}")
            await self._publish_error("review", str(e))
    
    # Strategy discovery handlers
    
    async def _handle_strategy_search(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy search event.
        
        Args:
            data: Search parameters including query, filters, etc.
        """
        try:
            if not data:
                data = {}
            
            query = data.get("query", "").lower()
            category = data.get("category")
            risk_level = data.get("risk_level")
            author = data.get("author")
            min_rating = data.get("min_rating")
            sort_by = data.get("sort_by", "rating")  # rating, popularity, newest
            approved_only = data.get("approved_only", True)
            
            # Filter strategies
            results = []
            
            for strategy_id, strategy in self.strategies.items():
                # Skip non-approved strategies if requested
                if approved_only and not strategy.get("approved", False):
                    continue
                
                # Apply text search
                if query and not (
                    query in strategy.get("name", "").lower() or
                    query in strategy.get("description", "").lower() or
                    query in strategy.get("tags", [])
                ):
                    continue
                
                # Apply category filter
                if category and strategy.get("category") != category:
                    continue
                
                # Apply risk level filter
                if risk_level and strategy.get("risk_level") != risk_level:
                    continue
                
                # Apply author filter
                if author and strategy.get("author") != author:
                    continue
                
                # Apply rating filter
                if min_rating is not None:
                    avg_rating = 0.0
                    if strategy_id in self.ratings:
                        ratings = self.ratings[strategy_id]
                        if ratings:
                            avg_rating = sum(r["rating"] for r in ratings.values()) / len(ratings)
                    
                    if avg_rating < min_rating:
                        continue
                
                # Add to results
                strategy_summary = {
                    "id": strategy_id,
                    "name": strategy.get("name", "Unnamed Strategy"),
                    "description": strategy.get("description", ""),
                    "author": strategy.get("author", "Unknown"),
                    "category": strategy.get("category", "Uncategorized"),
                    "risk_level": strategy.get("risk_level", "Medium"),
                    "version": strategy.get("version", "1.0.0"),
                    "created_at": strategy.get("created_at"),
                    "updated_at": strategy.get("updated_at"),
                    "downloads": self.download_stats.get(strategy_id, {}).get("count", 0),
                }
                
                # Add rating info
                if strategy_id in self.ratings:
                    ratings = self.ratings[strategy_id]
                    if ratings:
                        avg_rating = sum(r["rating"] for r in ratings.values()) / len(ratings)
                        strategy_summary["avg_rating"] = avg_rating
                        strategy_summary["rating_count"] = len(ratings)
                
                results.append(strategy_summary)
            
            # Sort results
            if sort_by == "rating":
                results.sort(key=lambda s: s.get("avg_rating", 0), reverse=True)
            elif sort_by == "popularity":
                results.sort(key=lambda s: s.get("downloads", 0), reverse=True)
            elif sort_by == "newest":
                results.sort(key=lambda s: s.get("created_at", ""), reverse=True)
            
            # Publish search results
            if self.event_bus:
                await self.publish_event("strategy.search_results", {
                    "query": query,
                    "filters": {
                        "category": category,
                        "risk_level": risk_level,
                        "author": author,
                        "min_rating": min_rating,
                        "approved_only": approved_only
                    },
                    "results": results,
                    "count": len(results),
                    "timestamp": datetime.now().isoformat()
                })
            
            self.logger.info(f"Strategy search: query='{query}', found {len(results)} results")
            try:
                if hasattr(self, "_emit_trading_telemetry"):
                    self._emit_trading_telemetry(
                        event_type="strategy_marketplace.search",
                        success=True,
                        metadata={
                            "query": query,
                            "result_count": len(results),
                        },
                    )
            except Exception:
                logger.debug("Telemetry error in _handle_strategy_search", exc_info=True)
            
        except Exception as e:
            self.logger.error(f"Error handling strategy search: {e}")
            await self._publish_error("search", str(e))
    
    async def _handle_strategy_browse(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy browse event.
        
        Args:
            data: Browse parameters including category, sorting, etc.
        """
        try:
            if not data:
                data = {}
            
            category = data.get("category")
            page = data.get("page", 1)
            page_size = data.get("page_size", 20)
            sort_by = data.get("sort_by", "featured")  # featured, rating, popularity, newest
            
            # Calculate pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            
            # Get strategies by category
            category_strategies = []
            
            for strategy_id, strategy in self.strategies.items():
                # Skip non-approved strategies
                if not strategy.get("approved", False):
                    continue
                
                # Apply category filter
                if category and strategy.get("category") != category:
                    continue
                
                # Add to results
                strategy_summary = {
                    "id": strategy_id,
                    "name": strategy.get("name", "Unnamed Strategy"),
                    "description": strategy.get("description", ""),
                    "author": strategy.get("author", "Unknown"),
                    "category": strategy.get("category", "Uncategorized"),
                    "risk_level": strategy.get("risk_level", "Medium"),
                    "version": strategy.get("version", "1.0.0"),
                    "thumbnail": strategy.get("thumbnail", None),
                    "downloads": self.download_stats.get(strategy_id, {}).get("count", 0),
                }
                
                # Add rating info
                if strategy_id in self.ratings:
                    ratings = self.ratings[strategy_id]
                    if ratings:
                        avg_rating = sum(r["rating"] for r in ratings.values()) / len(ratings)
                        strategy_summary["avg_rating"] = avg_rating
                        strategy_summary["rating_count"] = len(ratings)
                
                # Add performance stats if available
                if strategy_id in self.performance_stats:
                    perf = self.performance_stats[strategy_id]
                    strategy_summary["performance"] = {
                        "win_rate": perf.get("win_rate", 0.0),
                        "profit_factor": perf.get("profit_factor", 0.0),
                        "sharpe_ratio": perf.get("sharpe_ratio", 0.0),
                        "max_drawdown": perf.get("max_drawdown", 0.0)
                    }
                
                category_strategies.append(strategy_summary)
            
            # Sort results
            if sort_by == "featured":
                # Sort featured strategies first, then by rating
                category_strategies.sort(
                    key=lambda s: (s["id"] in self.featured_strategies, s.get("avg_rating", 0)), 
                    reverse=True
                )
            elif sort_by == "rating":
                category_strategies.sort(key=lambda s: s.get("avg_rating", 0), reverse=True)
            elif sort_by == "popularity":
                category_strategies.sort(key=lambda s: s.get("downloads", 0), reverse=True)
            elif sort_by == "newest":
                category_strategies.sort(key=lambda s: s.get("created_at", ""), reverse=True)
            
            # Apply pagination
            paginated_results = category_strategies[start_idx:end_idx]
            total_pages = (len(category_strategies) + page_size - 1) // page_size
            
            # Publish browse results
            await self.publish_event("strategy.browse_results", {
                "category": category,
                "sort_by": sort_by,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "total_results": len(category_strategies),
                "results": paginated_results,
                "timestamp": datetime.now().isoformat()
            })
            
            self.logger.info(f"Strategy browse: category='{category}', page={page}/{total_pages}, found {len(category_strategies)} strategies total")
            try:
                if hasattr(self, "_emit_trading_telemetry"):
                    self._emit_trading_telemetry(
                        event_type="strategy_marketplace.browse",
                        success=True,
                        metadata={
                            "category": category,
                            "page": page,
                            "page_size": page_size,
                            "total_results": len(category_strategies),
                        },
                    )
            except Exception:
                logger.debug("Telemetry error in _handle_strategy_browse", exc_info=True)
            
        except Exception as e:
            self.logger.error(f"Error handling strategy browse: {e}")
            await self._publish_error("browse", str(e))
    
    async def _handle_strategy_get_details(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy detail request event.
        
        Args:
            data: Strategy ID to get details for
        """
        try:
            if not data or "strategy_id" not in data:
                await self._publish_error("get_details", "Missing strategy_id in request")
                return
            
            strategy_id = data["strategy_id"]
            
            # Check if strategy exists
            if strategy_id not in self.strategies:
                await self._publish_error("get_details", f"Strategy with ID {strategy_id} not found")
                return
            
            # Get the strategy
            strategy = self.strategies[strategy_id]
            
            # Prepare response with full details
            details = {
                "id": strategy_id,
                "name": strategy.get("name", "Unnamed Strategy"),
                "description": strategy.get("description", ""),
                "long_description": strategy.get("long_description", ""),
                "author": strategy.get("author", "Unknown"),
                "author_profile": strategy.get("author_profile", {}),
                "category": strategy.get("category", "Uncategorized"),
                "risk_level": strategy.get("risk_level", "Medium"),
                "version": strategy.get("version", "1.0.0"),
                "created_at": strategy.get("created_at"),
                "updated_at": strategy.get("updated_at"),
                "thumbnail": strategy.get("thumbnail", None),
                "code": strategy.get("code", ""),
                "parameters": strategy.get("parameters", {}),
                "markets": strategy.get("markets", []),
                "timeframes": strategy.get("timeframes", []),
                "tags": strategy.get("tags", []),
                "downloads": self.download_stats.get(strategy_id, {}).get("count", 0),
                "installation_guide": strategy.get("installation_guide", ""),
                "usage_guide": strategy.get("usage_guide", ""),
                "changelog": strategy.get("changelog", []),
                "requires_api_keys": strategy.get("requires_api_keys", False),
                "required_apis": strategy.get("required_apis", []),
                "example_trades": strategy.get("example_trades", []),
                "backtest_results": strategy.get("backtest_results", {}),
            }
            
            # Add rating info
            if strategy_id in self.ratings:
                ratings = self.ratings[strategy_id]
                if ratings:
                    avg_rating = sum(r["rating"] for r in ratings.values()) / len(ratings)
                    details["avg_rating"] = avg_rating
                    details["rating_count"] = len(ratings)
                    
                    # Get rating distribution
                    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                    for r in ratings.values():
                        rating_val = int(r["rating"])
                        if rating_val in distribution:
                            distribution[rating_val] += 1
                    
                    details["rating_distribution"] = distribution
            
            # Add review info
            if strategy_id in self.reviews:
                reviews = self.reviews[strategy_id]
                details["reviews"] = [
                    {
                        "user_id": user_id,
                        "text": review["text"],
                        "timestamp": review["timestamp"]
                    }
                    for user_id, review in reviews.items()
                ]
            else:
                details["reviews"] = []
            
            # Add performance stats if available
            if strategy_id in self.performance_stats:
                details["performance"] = self.performance_stats[strategy_id]
            
            # Track download for analytics purposes
            user_id = data.get("user_id")
            if user_id:
                # Initialize if needed
                if strategy_id not in self.download_stats:
                    self.download_stats[strategy_id] = {"count": 0, "users": []}
                
                # Only count if user hasn't downloaded before
                if user_id not in self.download_stats[strategy_id]["users"]:
                    self.download_stats[strategy_id]["count"] += 1
                    self.download_stats[strategy_id]["users"].append(user_id)
                    await self._save_strategies()
            
            # Publish details
            if self.event_bus:
                await self.publish_event("strategy.details", {
                    "strategy_id": strategy_id,
                    "details": details,
                    "timestamp": datetime.now().isoformat()
                })
            
            self.logger.info(f"Strategy details requested: {strategy['name']} (ID: {strategy_id})")
            try:
                if hasattr(self, "_emit_trading_telemetry"):
                    self._emit_trading_telemetry(
                        event_type="strategy_marketplace.get_details",
                        success=True,
                        metadata={
                            "strategy_id": strategy_id,
                            "has_backtest": bool(details.get("backtest_results")),
                        },
                    )
            except Exception:
                logger.debug("Telemetry error in _handle_strategy_get_details", exc_info=True)
            
        except Exception as e:
            self.logger.error(f"Error handling strategy details request: {e}")
            await self._publish_error("get_details", str(e))
    
    # Strategy subscription handlers
    
    async def _handle_strategy_subscribe(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy subscription event.
        
        Args:
            data: Subscription data including strategy ID and user ID
        """
        try:
            if not data or "strategy_id" not in data or "user_id" not in data:
                await self._publish_error("subscribe", "Missing strategy_id or user_id in request")
                return
            
            strategy_id = data["strategy_id"]
            user_id = data["user_id"]
            
            # Check if strategy exists
            if strategy_id not in self.strategies:
                await self._publish_error("subscribe", f"Strategy with ID {strategy_id} not found")
                return
            
            # Initialize user subscriptions if needed
            if user_id not in self.user_subscriptions:
                self.user_subscriptions[user_id] = []
            
            # Check if already subscribed
            if strategy_id in self.user_subscriptions[user_id]:
                await self._publish_error("subscribe", f"Already subscribed to strategy {strategy_id}")
                return
            
            # Add subscription
            self.user_subscriptions[user_id].append(strategy_id)
            
            # Save strategies
            await self._save_strategies()
            
            # Get strategy info for response
            strategy = self.strategies[strategy_id]
            
            # Publish subscription event
            if self.event_bus:
                await self.publish_event("strategy.subscribed", {
                    "strategy_id": strategy_id,
                    "name": strategy["name"],
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                })
            
            # If Copy Trading is connected, register as trader to follow
            if self.copy_trading:
                try:
                    # Create a copy trading subscription using the strategy as a "trader"
                    await self.event_bus.publish("copy_trading.subscribe", {
                        "trader_id": f"strategy_{strategy_id}",
                        "alias": f"Strategy: {strategy['name']}",
                        "risk_level": strategy.get("risk_level", "medium").lower(),
                        "allocation": data.get("allocation", 0.1)  # Default 10% allocation
                    })
                    self.logger.info(f"Registered strategy {strategy['name']} with Copy Trading system for user {user_id}")
                except Exception as e:
                    self.logger.error(f"Error registering strategy with Copy Trading system: {e}")
            
            self.logger.info(f"User {user_id} subscribed to strategy: {strategy['name']} (ID: {strategy_id})")
            try:
                if hasattr(self, "_emit_trading_telemetry"):
                    self._emit_trading_telemetry(
                        event_type="strategy_marketplace.subscribe",
                        success=True,
                        metadata={
                            "strategy_id": strategy_id,
                            "user_id": user_id,
                        },
                    )
            except Exception:
                logger.debug("Telemetry error in _handle_strategy_subscribe", exc_info=True)
            
        except Exception as e:
            self.logger.error(f"Error handling strategy subscription: {e}")
            await self._publish_error("subscribe", str(e))
    
    async def _handle_strategy_unsubscribe(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy unsubscription event.
        
        Args:
            data: Unsubscription data including strategy ID and user ID
        """
        try:
            if not data or "strategy_id" not in data or "user_id" not in data:
                await self._publish_error("unsubscribe", "Missing strategy_id or user_id in request")
                return
            
            strategy_id = data["strategy_id"]
            user_id = data["user_id"]
            
            # Check if user has subscriptions
            if user_id not in self.user_subscriptions:
                await self._publish_error("unsubscribe", f"User {user_id} has no subscriptions")
                return
            
            # Check if subscribed to this strategy
            if strategy_id not in self.user_subscriptions[user_id]:
                await self._publish_error("unsubscribe", f"Not subscribed to strategy {strategy_id}")
                return
            
            # Get strategy info for logging
            strategy_name = "Unknown Strategy"
            if strategy_id in self.strategies:
                strategy_name = self.strategies[strategy_id]["name"]
            
            # Remove subscription
            self.user_subscriptions[user_id].remove(strategy_id)
            
            # Save strategies
            await self._save_strategies()
            
            # Publish unsubscription event
            if self.event_bus:
                await self.publish_event("strategy.unsubscribed", {
                    "strategy_id": strategy_id,
                    "name": strategy_name,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                })
            
            # If Copy Trading is connected, unregister from trader to follow
            if self.copy_trading:
                try:
                    # Remove the copy trading subscription
                    await self.publish_event("copy_trading.unsubscribe", {
                        "trader_id": f"strategy_{strategy_id}"
                    })
                    self.logger.info(f"Unregistered strategy {strategy_name} from Copy Trading system for user {user_id}")
                except Exception as e:
                    self.logger.error(f"Error unregistering strategy from Copy Trading system: {e}")
            
            self.logger.info(f"User {user_id} unsubscribed from strategy: {strategy_name} (ID: {strategy_id})")
            try:
                if hasattr(self, "_emit_trading_telemetry"):
                    self._emit_trading_telemetry(
                        event_type="strategy_marketplace.unsubscribe",
                        success=True,
                        metadata={
                            "strategy_id": strategy_id,
                            "user_id": user_id,
                        },
                    )
            except Exception:
                logger.debug("Telemetry error in _handle_strategy_unsubscribe", exc_info=True)
            
        except Exception as e:
            self.logger.error(f"Error handling strategy unsubscription: {e}")
            await self._publish_error("unsubscribe", str(e))
    
    async def _publish_error(self, operation: str, error_message: str) -> None:
        """
        Publish an error message to the event bus.
        
        Args:
            operation: The operation that failed
            error_message: The error message
        """
        if self.event_bus:
            await self.publish_event("strategy.error", {
                "operation": operation,
                "error": error_message,
                "timestamp": datetime.now().isoformat()
            })
            
        # Telemetry: centralized error reporting
        try:
            if hasattr(self, "_emit_trading_telemetry"):
                self._emit_trading_telemetry(
                    event_type=f"strategy_marketplace.{operation}_error",
                    success=False,
                    error=error_message,
                    metadata={"operation": operation},
                )
        except Exception:
            logger.debug("Telemetry error in _publish_error", exc_info=True)

        self.logger.error(f"Strategy Marketplace error in {operation}: {error_message}")
