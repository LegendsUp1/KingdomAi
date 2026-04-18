#!/usr/bin/env python3
"""
Strategy Repository for Kingdom AI Strategy Marketplace

This module provides storage and retrieval functionality for trading strategies
in the Strategy Marketplace.
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("KingdomAI.StrategyRepository")

class StrategyRepository:
    """
    Repository for storing and retrieving trading strategies.
    
    This component manages the persistent storage of strategies and their metadata,
    providing CRUD operations for the Strategy Marketplace.
    """
    
    def __init__(self, config=None):
        """
        Initialize the strategy repository.
        
        Args:
            config: Configuration settings for the repository
        """
        self.config = config or {}
        self.logger = logger
        
        # Storage settings
        self.data_dir = self.config.get("data_dir", "data/strategies")
        self.index_file = os.path.join(self.data_dir, "index.json")
        self.backup_dir = os.path.join(self.data_dir, "backups")
        
        # Create directories if they don't exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Strategy index
        self.index = {}
        self.load_index()
        
    def load_index(self) -> bool:
        """
        Load the strategy index from disk.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if os.path.exists(self.index_file):
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self.index = json.load(f)
                    self.logger.info(f"Loaded strategy index with {len(self.index)} strategies")
                return True
            else:
                self.logger.info("No strategy index found, creating empty index")
                self.save_index()
                return True
        except Exception as e:
            self.logger.error(f"Error loading strategy index: {e}")
            return False
    
    def save_index(self) -> bool:
        """
        Save the strategy index to disk.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Error saving strategy index: {e}")
            return False
    
    def create_backup(self) -> Optional[str]:
        """
        Create a backup of the strategy index.
        
        Returns:
            Optional[str]: Backup filename if successful, None otherwise
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            backup_file = os.path.join(self.backup_dir, f"index_{timestamp}.json")
            
            with open(self.index_file, 'r', encoding='utf-8') as src:
                with open(backup_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
                    
            self.logger.info(f"Created strategy index backup: {backup_file}")
            return backup_file
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return None
    
    async def get_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a strategy by ID.
        
        Args:
            strategy_id: ID of the strategy to retrieve
            
        Returns:
            Optional[Dict[str, Any]]: Strategy data if found, None otherwise
        """
        try:
            if strategy_id not in self.index:
                self.logger.warning(f"Strategy not found: {strategy_id}")
                return None
                
            strategy_file = os.path.join(self.data_dir, f"{strategy_id}.json")
            
            if not os.path.exists(strategy_file):
                self.logger.error(f"Strategy file missing: {strategy_file}")
                return None
                
            with open(strategy_file, 'r', encoding='utf-8') as f:
                strategy = json.load(f)
                
            return strategy
        except Exception as e:
            self.logger.error(f"Error getting strategy {strategy_id}: {e}")
            return None
    
    async def get_all_strategies(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all strategies.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of all strategies indexed by ID
        """
        strategies = {}
        
        for strategy_id in self.index:
            strategy = await self.get_strategy(strategy_id)
            if strategy:
                strategies[strategy_id] = strategy
                
        return strategies
    
    async def save_strategy(self, strategy_id: str, strategy: Dict[str, Any]) -> bool:
        """
        Save a strategy to the repository.
        
        Args:
            strategy_id: ID of the strategy
            strategy: Strategy data to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Update the index
            self.index[strategy_id] = {
                "id": strategy_id,
                "name": strategy.get("name", "Unnamed Strategy"),
                "author": strategy.get("author", "Unknown"),
                "category": strategy.get("category", "Uncategorized"),
                "risk_level": strategy.get("risk_level", "Medium"),
                "created_at": strategy.get("created_at", datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat()
            }
            
            # Save the index
            self.save_index()
            
            # Save the full strategy
            strategy_file = os.path.join(self.data_dir, f"{strategy_id}.json")
            with open(strategy_file, 'w', encoding='utf-8') as f:
                json.dump(strategy, f, indent=2)
                
            self.logger.info(f"Saved strategy: {strategy.get('name', 'Unnamed')} (ID: {strategy_id})")
            return True
        except Exception as e:
            self.logger.error(f"Error saving strategy {strategy_id}: {e}")
            return False
    
    async def delete_strategy(self, strategy_id: str) -> bool:
        """
        Delete a strategy from the repository.
        
        Args:
            strategy_id: ID of the strategy to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if strategy_id not in self.index:
                self.logger.warning(f"Strategy not found for deletion: {strategy_id}")
                return False
                
            # Create backup before deletion
            self.create_backup()
                
            # Remove from index
            strategy_name = self.index[strategy_id].get("name", "Unnamed")
            del self.index[strategy_id]
            
            # Save the index
            self.save_index()
            
            # Delete the strategy file
            strategy_file = os.path.join(self.data_dir, f"{strategy_id}.json")
            if os.path.exists(strategy_file):
                os.remove(strategy_file)
                
            self.logger.info(f"Deleted strategy: {strategy_name} (ID: {strategy_id})")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting strategy {strategy_id}: {e}")
            return False
    
    async def update_strategy_metadata(self, strategy_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update metadata for a strategy in the index.
        
        Args:
            strategy_id: ID of the strategy
            metadata: Metadata to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if strategy_id not in self.index:
                self.logger.warning(f"Strategy not found for metadata update: {strategy_id}")
                return False
                
            # Update metadata
            for key, value in metadata.items():
                if key != "id":  # Don't allow changing the ID
                    self.index[strategy_id][key] = value
                    
            # Always update the timestamp
            self.index[strategy_id]["updated_at"] = datetime.now().isoformat()
            
            # Save the index
            self.save_index()
            
            self.logger.info(f"Updated metadata for strategy: {self.index[strategy_id].get('name', 'Unnamed')} (ID: {strategy_id})")
            return True
        except Exception as e:
            self.logger.error(f"Error updating strategy metadata {strategy_id}: {e}")
            return False
    
    async def search_strategies(self, query=None, filters=None) -> List[Dict[str, Any]]:
        """
        Search for strategies matching the given query and filters.
        
        Args:
            query: Search text
            filters: Dictionary of filters to apply
            
        Returns:
            List[Dict[str, Any]]: List of matching strategies
        """
        try:
            results = []
            
            query = query.lower() if query else ""
            filters = filters or {}
            
            for strategy_id, metadata in self.index.items():
                # Skip if doesn't match text search
                if query and not (
                    query in metadata.get("name", "").lower() or
                    query in metadata.get("author", "").lower() or
                    query in metadata.get("category", "").lower()
                ):
                    continue
                    
                # Apply filters
                if filters.get("category") and metadata.get("category") != filters["category"]:
                    continue
                    
                if filters.get("risk_level") and metadata.get("risk_level") != filters["risk_level"]:
                    continue
                    
                if filters.get("author") and metadata.get("author") != filters["author"]:
                    continue
                
                # Add to results
                results.append(metadata)
                
            return results
        except Exception as e:
            self.logger.error(f"Error searching strategies: {e}")
            return []
            
    async def get_strategies_by_author(self, author: str) -> List[Dict[str, Any]]:
        """
        Get all strategies by a specific author.
        
        Args:
            author: Author name or ID
            
        Returns:
            List[Dict[str, Any]]: List of strategies by the author
        """
        try:
            results = []
            
            for strategy_id, metadata in self.index.items():
                if metadata.get("author") == author:
                    results.append(metadata)
                    
            return results
        except Exception as e:
            self.logger.error(f"Error getting strategies by author {author}: {e}")
            return []
