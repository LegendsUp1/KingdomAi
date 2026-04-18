#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MetaLearning component for Kingdom AI.
Enables the system to learn from interactions and adapt its behavior.
"""

# Import meta learning components from fix files
try:
    from ..fix_meta_learning_part1 import (
        AdaptiveModelManager, ReinforcementLearner, PatternRecognizer,
        FeedbackProcessor, InteractionMemory, BehaviorOptimizer, 
        TransferLearningModule, UserPreferenceTracker
    )
    HAS_FIX_MODULES = True
except ImportError:
    try:
        from fix_meta_learning_part1 import (
            AdaptiveModelManager, ReinforcementLearner, PatternRecognizer,
            FeedbackProcessor, InteractionMemory, BehaviorOptimizer,
            TransferLearningModule, UserPreferenceTracker
        )
        HAS_FIX_MODULES = True
    except ImportError:
        HAS_FIX_MODULES = False

# Initialization function that 4keys.py expects
async def initialize_meta_learning_components(event_bus):
    """
    Initialize meta learning components and connect to the event bus.
    
    Args:
        event_bus: Event bus instance for component communication
        
    Returns:
        Dictionary of initialized components
    """
    logger = logging.getLogger("kingdom_ai")
    logger.info("Initializing meta learning components")
    components = {}
    
    try:
        # Create main meta learning system
        main_meta_learning = MetaLearning(event_bus=event_bus)
        components["meta_learning"] = main_meta_learning
        
        # Initialize subcomponents if fix modules are available
        if HAS_FIX_MODULES:
            # Adaptive Model Manager
            adaptive_model = AdaptiveModelManager(event_bus=event_bus)
            components["adaptive_model"] = adaptive_model
            
            # Reinforcement Learner
            reinforcement_learner = ReinforcementLearner(event_bus=event_bus)
            components["reinforcement_learner"] = reinforcement_learner
            
            # Pattern Recognizer
            pattern_recognizer = PatternRecognizer(event_bus=event_bus)
            components["pattern_recognizer"] = pattern_recognizer
            
            # Feedback Processor
            feedback_processor = FeedbackProcessor(event_bus=event_bus)
            components["feedback_processor"] = feedback_processor
            
            # Interaction Memory
            interaction_memory = InteractionMemory(event_bus=event_bus)
            components["interaction_memory"] = interaction_memory
            
            # Behavior Optimizer
            behavior_optimizer = BehaviorOptimizer(event_bus=event_bus)
            components["behavior_optimizer"] = behavior_optimizer
            
            # Transfer Learning Module
            transfer_learning = TransferLearningModule(event_bus=event_bus)
            components["transfer_learning"] = transfer_learning
            
            # User Preference Tracker
            preference_tracker = UserPreferenceTracker(event_bus=event_bus)
            components["preference_tracker"] = preference_tracker
        
        # Register event handlers for main meta learning
        if hasattr(event_bus, 'register_handler'):
            event_bus.register_handler("meta.learn_interaction", main_meta_learning.learn_from_interaction)
            event_bus.register_handler("meta.get_recommendations", main_meta_learning.get_recommendations)
            event_bus.register_handler("meta.store_preference", main_meta_learning.store_user_preference)
            event_bus.register_handler("meta.optimize_behavior", main_meta_learning.optimize_behavior)
        elif hasattr(event_bus, 'subscribe'):
            event_bus.subscribe("meta.learn_interaction", main_meta_learning.learn_from_interaction)
            event_bus.subscribe("meta.get_recommendations", main_meta_learning.get_recommendations)
            event_bus.subscribe("meta.store_preference", main_meta_learning.store_user_preference)
            event_bus.subscribe("meta.optimize_behavior", main_meta_learning.optimize_behavior)
            
        # Register additional handlers if fix modules are available
        if HAS_FIX_MODULES and hasattr(event_bus, 'register_handler'):
            event_bus.register_handler("meta.adaptive_model", adaptive_model.adapt_model)
            event_bus.register_handler("meta.pattern_recognition", pattern_recognizer.identify_patterns)
            event_bus.register_handler("meta.process_feedback", feedback_processor.process_feedback)
            event_bus.register_handler("meta.optimize", behavior_optimizer.optimize)
        elif HAS_FIX_MODULES and hasattr(event_bus, 'subscribe'):
            event_bus.subscribe("meta.adaptive_model", adaptive_model.adapt_model)
            event_bus.subscribe("meta.pattern_recognition", pattern_recognizer.identify_patterns)
            event_bus.subscribe("meta.process_feedback", feedback_processor.process_feedback)
            event_bus.subscribe("meta.optimize", behavior_optimizer.optimize)
        
        # Set all components as initialized
        for component_name, component in components.items():
            if hasattr(component, 'initialized'):
                component.initialized = True
                
        logger.info(f"Meta learning system initialized with {len(components)} components")
    except Exception as e:
        logger.error(f"Error initializing meta learning components: {e}")
    
    return components

import os
import logging
import json
import asyncio
import pickle
from datetime import datetime
from collections import defaultdict, deque

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class MetaLearning(BaseComponent):
    """
    Component for meta-learning capabilities.
    Allows Kingdom AI to learn from interactions and adapt.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the MetaLearning component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus, config)
        self.name = "MetaLearning"
        self.description = "Meta-learning and adaptation system"
        
        # Configuration
        self.learning_enabled = self.config.get("learning_enabled", True)
        self.data_dir = self.config.get("data_dir", os.path.join(os.path.dirname(__file__), "..", "data", "learning"))
        self.max_history = self.config.get("max_history", 1000)
        self.save_interval = self.config.get("save_interval", 300)  # seconds
        
        # Learning data
        self.interaction_history = deque(maxlen=self.max_history)
        self.user_preferences = {}
        self.learned_patterns = defaultdict(int)
        self.command_success_rates = {}
        
        # Status
        self.is_initialized = False
        self.save_task = None
        
    async def initialize(self):
        """Initialize the MetaLearning component."""
        logger.info("Initializing MetaLearning")
        
        if not self.learning_enabled:
            logger.info("Meta-learning is disabled in configuration")
            return
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Load saved learning data
        await self._load_learning_data()
        
        # Subscribe to events
        self.event_bus.subscribe("ai.query", self.on_ai_query)
        self.event_bus.subscribe("ai.response", self.on_ai_response)
        self.event_bus.subscribe("user.feedback", self.on_user_feedback)
        self.event_bus.subscribe("command.executed", self.on_command_executed)
        self.event_bus.subscribe("trading.order.result", self.on_trading_result)
        self.event_bus.subscribe("meta.learn", self.on_learn)
        self.event_bus.subscribe("meta.reset", self.on_reset)
        self.event_bus.subscribe("system.shutdown", self.on_shutdown)
        
        # Start periodic save task
        self.save_task = asyncio.create_task(self._save_periodically())
        
        self.is_initialized = True
        logger.info("MetaLearning initialized")
        
    async def _load_learning_data(self):
        """Load saved learning data from disk."""
        try:
            # Load user preferences
            preferences_path = os.path.join(self.data_dir, "user_preferences.json")
            if os.path.exists(preferences_path):
                with open(preferences_path, "r") as f:
                    self.user_preferences = json.load(f)
                logger.info(f"Loaded {len(self.user_preferences)} user preferences")
            
            # Load learned patterns
            patterns_path = os.path.join(self.data_dir, "learned_patterns.pkl")
            if os.path.exists(patterns_path):
                with open(patterns_path, "rb") as f:
                    self.learned_patterns = pickle.load(f)
                logger.info(f"Loaded {len(self.learned_patterns)} learned patterns")
            
            # Load command success rates
            success_rates_path = os.path.join(self.data_dir, "command_success_rates.json")
            if os.path.exists(success_rates_path):
                with open(success_rates_path, "r") as f:
                    self.command_success_rates = json.load(f)
                logger.info(f"Loaded success rates for {len(self.command_success_rates)} commands")
            
            # Load interaction history
            history_path = os.path.join(self.data_dir, "interaction_history.json")
            if os.path.exists(history_path):
                with open(history_path, "r") as f:
                    history_data = json.load(f)
                self.interaction_history = deque(history_data, maxlen=self.max_history)
                logger.info(f"Loaded {len(self.interaction_history)} interaction history entries")
        
        except Exception as e:
            logger.error(f"Error loading learning data: {e}")
            # Continue with empty data structures
    
    async def _save_learning_data(self):
        """Save learning data to disk."""
        if not self.learning_enabled or not self.is_initialized:
            return
            
        try:
            # Save user preferences
            preferences_path = os.path.join(self.data_dir, "user_preferences.json")
            with open(preferences_path, "w") as f:
                json.dump(self.user_preferences, f, indent=2)
            
            # Save learned patterns
            patterns_path = os.path.join(self.data_dir, "learned_patterns.pkl")
            with open(patterns_path, "wb") as f:
                pickle.dump(dict(self.learned_patterns), f)
            
            # Save command success rates
            success_rates_path = os.path.join(self.data_dir, "command_success_rates.json")
            with open(success_rates_path, "w") as f:
                json.dump(self.command_success_rates, f, indent=2)
            
            # Save interaction history
            history_path = os.path.join(self.data_dir, "interaction_history.json")
            with open(history_path, "w") as f:
                json.dump(list(self.interaction_history), f, indent=2)
            
            logger.info("Saved learning data")
        except Exception as e:
            logger.error(f"Error saving learning data: {e}")
    
    async def _save_periodically(self):
        """Periodically save learning data."""
        try:
            while True:
                await asyncio.sleep(self.save_interval)
                await self._save_learning_data()
        except asyncio.CancelledError:
            # Save one last time before exiting
            await self._save_learning_data()
    
    async def record_interaction(self, interaction_type, data):
        """
        Record an interaction in the history.
        
        Args:
            interaction_type: Type of interaction
            data: Interaction data
        """
        if not self.learning_enabled or not self.is_initialized:
            return
            
        # Add timestamp
        data["timestamp"] = datetime.now().isoformat()
        data["type"] = interaction_type
        
        # Add to history
        self.interaction_history.append(data)
        
        # Analyze patterns if applicable
        if interaction_type in ["ai.query", "command.executed", "trading.order"]:
            await self._analyze_patterns(data)
    
    async def _analyze_patterns(self, data):
        """
        Analyze patterns in interactions.
        
        Args:
            data: Interaction data
        """
        # This is a simple implementation that could be expanded
        # For now, just track command frequencies
        if "command" in data:
            command = data["command"]
            self.learned_patterns[command] += 1
        elif "query" in data:
            query = data["query"]
            # Simple keyword extraction
            words = query.lower().split()
            for word in words:
                if len(word) > 3:  # Skip short words
                    self.learned_patterns[word] += 1
    
    async def update_user_preference(self, category, key, value):
        """
        Update a user preference.
        
        Args:
            category: Preference category
            key: Preference key
            value: Preference value
        """
        if not self.learning_enabled or not self.is_initialized:
            return
            
        if category not in self.user_preferences:
            self.user_preferences[category] = {}
        
        self.user_preferences[category][key] = value
        logger.info(f"Updated user preference: {category}.{key} = {value}")
    
    async def get_user_preference(self, category, key, default=None):
        """
        Get a user preference.
        
        Args:
            category: Preference category
            key: Preference key
            default: Default value if not found
            
        Returns:
            Preference value or default
        """
        if not self.learning_enabled or not self.is_initialized:
            return default
            
        if category not in self.user_preferences:
            return default
        
        return self.user_preferences[category].get(key, default)
    
    async def update_command_success(self, command, success):
        """
        Update command success rate.
        
        Args:
            command: Command name
            success: Whether the command succeeded
        """
        if not self.learning_enabled or not self.is_initialized:
            return
            
        if command not in self.command_success_rates:
            self.command_success_rates[command] = {
                "successes": 0,
                "failures": 0,
                "total": 0
            }
        
        self.command_success_rates[command]["total"] += 1
        if success:
            self.command_success_rates[command]["successes"] += 1
        else:
            self.command_success_rates[command]["failures"] += 1
    
    async def get_command_success_rate(self, command):
        """
        Get success rate for a command.
        
        Args:
            command: Command name
            
        Returns:
            Success rate (0.0 to 1.0) or None if no data
        """
        if not self.learning_enabled or not self.is_initialized:
            return None
            
        if command not in self.command_success_rates:
            return None
        
        stats = self.command_success_rates[command]
        if stats["total"] == 0:
            return 0.0
        
        return stats["successes"] / stats["total"]
    
    async def get_popular_commands(self, limit=5):
        """
        Get most popular commands.
        
        Args:
            limit: Maximum number of commands to return
            
        Returns:
            List of (command, frequency) tuples
        """
        if not self.learning_enabled or not self.is_initialized:
            return []
            
        # Filter for commands only
        commands = {k: v for k, v in self.learned_patterns.items() 
                   if k in self.command_success_rates}
        
        # Sort by frequency
        sorted_commands = sorted(commands.items(), key=lambda x: x[1], reverse=True)
        
        return sorted_commands[:limit]
    
    async def on_ai_query(self, data):
        """
        Handle AI query event.
        
        Args:
            data: Query data
        """
        await self.record_interaction("ai.query", {
            "query": data.get("message", ""),
            "source": data.get("source", "unknown")
        })
    
    async def on_ai_response(self, data):
        """
        Handle AI response event.
        
        Args:
            data: Response data
        """
        await self.record_interaction("ai.response", {
            "response": data.get("message", ""),
            "source": data.get("source", "unknown")
        })
    
    async def on_user_feedback(self, data):
        """
        Handle user feedback event.
        
        Args:
            data: Feedback data
        """
        feedback_type = data.get("type", "general")
        value = data.get("value")
        
        await self.record_interaction("user.feedback", {
            "type": feedback_type,
            "value": value
        })
        
        # Update user preferences based on feedback
        if feedback_type.startswith("preference."):
            category, key = feedback_type.split(".", 1)[1].split(".", 1)
            await self.update_user_preference(category, key, value)
    
    async def on_command_executed(self, data):
        """
        Handle command executed event.
        
        Args:
            data: Command data
        """
        command = data.get("command", "")
        success = data.get("success", True)
        
        await self.record_interaction("command.executed", {
            "command": command,
            "success": success,
            "duration": data.get("duration", 0)
        })
        
        await self.update_command_success(command, success)
    
    async def on_trading_result(self, data):
        """
        Handle trading result event.
        
        Args:
            data: Trading result data
        """
        order_type = data.get("type", "")
        success = data.get("success", False)
        profit = data.get("profit", 0)
        
        await self.record_interaction("trading.result", {
            "type": order_type,
            "success": success,
            "profit": profit,
            "symbol": data.get("symbol", "")
        })
        
        # Update trading preferences based on results
        if success and profit > 0:
            await self.update_user_preference("trading", f"preferred_{order_type}", data.get("symbol", ""))
    
    async def on_learn(self, data):
        """
        Handle explicit learn event.
        
        Args:
            data: Learning data
        """
        category = data.get("category", "")
        key = data.get("key", "")
        value = data.get("value")
        
        if not category or not key:
            logger.warning("Received incomplete learn request")
            return
        
        await self.update_user_preference(category, key, value)
        
        await self.event_bus.publish("meta.learn.result", {
            "success": True,
            "category": category,
            "key": key,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_reset(self, data):
        """
        Handle reset event.
        
        Args:
            data: Reset data
        """
        reset_type = data.get("type", "all")
        
        if reset_type == "preferences":
            self.user_preferences = {}
            logger.info("Reset user preferences")
        elif reset_type == "patterns":
            self.learned_patterns = defaultdict(int)
            logger.info("Reset learned patterns")
        elif reset_type == "success_rates":
            self.command_success_rates = {}
            logger.info("Reset command success rates")
        elif reset_type == "history":
            self.interaction_history.clear()
            logger.info("Reset interaction history")
        else:  # all
            self.user_preferences = {}
            self.learned_patterns = defaultdict(int)
            self.command_success_rates = {}
            self.interaction_history.clear()
            logger.info("Reset all learning data")
        
        # Save the reset state
        await self._save_learning_data()
        
        await self.event_bus.publish("meta.reset.result", {
            "success": True,
            "type": reset_type,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the MetaLearning component."""
        logger.info("Shutting down MetaLearning")
        
        # Cancel save task
        if self.save_task:
            self.save_task.cancel()
            try:
                await self.save_task
            except asyncio.CancelledError:
                pass
        
        # Save data one last time
        await self._save_learning_data()
        
        logger.info("MetaLearning shut down successfully")
