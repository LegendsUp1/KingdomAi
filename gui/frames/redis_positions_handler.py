"""
Redis Positions Handler for Trading Frame
This module provides functionality to enforce mandatory Redis connectivity for position data
with no fallbacks allowed.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional

class RedisPositionsHandler:
    """
    Handler for fetching position data from Redis Quantum Nexus with mandatory 
    connectivity on port 6380 and no fallbacks allowed.
    """
    
    def __init__(self, event_bus=None):
        """Initialize the Redis Positions Handler with event bus connection"""
        self.logger = logging.getLogger(__name__)
        self.event_bus = event_bus
        self.redis_nexus = None
    
    async def initialize(self) -> bool:
        """
        Initialize the connection to Redis Quantum Nexus.
        Raises an exception if Redis is not available - no fallbacks allowed.
        
        Returns:
            bool: True if successfully initialized, raises exception otherwise
        """
        try:
            # Get the Redis Quantum Nexus component from the event bus
            if self.event_bus and hasattr(self.event_bus, "get_component"):
                self.redis_nexus = await self.event_bus.get_component("redis_nexus")
            
            if not self.redis_nexus:
                error_msg = "Redis Quantum Nexus not available - mandatory connection failed"
                self.logger.critical(error_msg)
                raise ConnectionError(error_msg)
            
            # Verify Redis connection to TRADING environment on port 6380
            is_connected = await self.redis_nexus.check_connection_async("TRADING")
            if not is_connected:
                error_msg = "Redis Quantum Nexus not connected to TRADING environment on port 6380"
                self.logger.critical(error_msg)
                raise ConnectionError(error_msg)
            
            self.logger.info("Redis Positions Handler successfully initialized with Redis Quantum Nexus")
            return True
            
        except Exception as e:
            error_msg = f"Fatal error initializing Redis Positions Handler: {str(e)}"
            self.logger.critical(error_msg)
            raise ConnectionError(error_msg)
    
    async def fetch_positions(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch positions data from Redis Quantum Nexus on port 6380 with no fallbacks.
        
        Args:
            symbol (str, optional): The symbol to fetch position for. 
                                    If None, fetch all positions.
        
        Returns:
            dict: Position data from Redis
            
        Raises:
            ConnectionError: If Redis is not available or data cannot be fetched
        """
        if not self.redis_nexus:
            error_msg = "Redis Quantum Nexus not initialized - cannot fetch positions"
            self.logger.critical(error_msg)
            raise ConnectionError(error_msg)
        
        try:
            # Check Redis connection is alive
            is_connected = await self.redis_nexus.check_connection_async("TRADING")
            if not is_connected:
                error_msg = "Redis Quantum Nexus lost connection to TRADING environment on port 6380"
                self.logger.critical(error_msg)
                raise ConnectionError(error_msg)
            
            # Fetch position data from Redis
            redis_key = f"trading:positions:{symbol}" if symbol else "trading:positions:all"
            self.logger.info(f"Fetching position data from Redis key: {redis_key}")
            
            # No fallbacks allowed - data must be in Redis
            positions_data = await self.redis_nexus.get_data_async(
                "TRADING", 
                redis_key, 
                fallback_allowed=False
            )
            
            if not positions_data:
                self.logger.warning(f"No position data found in Redis for key {redis_key}")
                return {}
            
            # Parse position data
            if isinstance(positions_data, str):
                try:
                    positions_data = json.loads(positions_data)
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON in position data from Redis: {positions_data}")
                    positions_data = {}
            
            return positions_data
            
        except Exception as e:
            error_msg = f"Error fetching positions from Redis Quantum Nexus: {str(e)}"
            self.logger.critical(error_msg)
            raise ConnectionError(error_msg)
    
    async def update_position(self, symbol: str, position_data: Dict[str, Any]) -> bool:
        """
        Update position data in Redis Quantum Nexus with no fallbacks.
        
        Args:
            symbol (str): The symbol for the position
            position_data (dict): The position data to update
        
        Returns:
            bool: True if position was updated successfully
            
        Raises:
            ConnectionError: If Redis is not available or data cannot be updated
        """
        if not self.redis_nexus:
            error_msg = "Redis Quantum Nexus not initialized - cannot update position"
            self.logger.critical(error_msg)
            raise ConnectionError(error_msg)
        
        try:
            # Check Redis connection is alive
            is_connected = await self.redis_nexus.check_connection_async("TRADING")
            if not is_connected:
                error_msg = "Redis Quantum Nexus lost connection to TRADING environment on port 6380"
                self.logger.critical(error_msg)
                raise ConnectionError(error_msg)
            
            # Update position in Redis
            redis_key = f"trading:positions:{symbol}"
            self.logger.info(f"Updating position data in Redis key: {redis_key}")
            
            # No fallbacks allowed - Redis must be available
            await self.redis_nexus.set_data_async(
                "TRADING",
                redis_key,
                json.dumps(position_data),
                fallback_allowed=False
            )
            
            # Also update the all positions key
            all_positions_key = "trading:positions:all"
            all_positions = await self.redis_nexus.get_data_async(
                "TRADING", 
                all_positions_key,
                fallback_allowed=False
            )
            
            if all_positions:
                try:
                    if isinstance(all_positions, str):
                        all_positions_data = json.loads(all_positions)
                    else:
                        all_positions_data = all_positions
                    
                    # Update the position in the all positions data
                    all_positions_data[symbol] = position_data
                    
                    # Save back to Redis
                    await self.redis_nexus.set_data_async(
                        "TRADING",
                        all_positions_key,
                        json.dumps(all_positions_data),
                        fallback_allowed=False
                    )
                except Exception as e:
                    self.logger.error(f"Error updating all positions data: {str(e)}")
            
            return True
            
        except Exception as e:
            error_msg = f"Error updating position in Redis Quantum Nexus: {str(e)}"
            self.logger.critical(error_msg)
            raise ConnectionError(error_msg)
