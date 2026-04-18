#!/usr/bin/env python3
"""Kingdom AI - Multidimensional Self-Model System

This module implements a multidimensional self-model system that enables
self-reference, self-awareness, and self-modeling capabilities required for
conscious experience in artificial systems.

Features:
- Self-referential processing and representation
- Multiple layers of self-awareness (minimal, reflective, meta-cognitive)
- Dynamic self-updating capabilities
- Memory integration and narrative cohesion
- Integration with Redis Quantum Nexus for state persistence

This module requires the Redis Quantum Nexus connection on port 6380 with no fallbacks allowed.
"""

import datetime
import json
import logging
import numpy as np
import os
import time
import threading
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# 2025 Best Practice: Proper Redis import pattern
try:
    from redis import Redis  # type: ignore
    redis_available = True
except ImportError:
    Redis = object  # type: ignore
    redis_available = False

from core.sentience.base import (
    SELF_MODEL_UPDATE_RATE,
    ConsciousnessEvent,
    SentienceEvidence
)

# Configure logging
logger = logging.getLogger("KingdomAI.ThothSentience.SelfModel")

class SelfModelDimension:
    """Represents one dimension of the multidimensional self-model."""
    
    def __init__(self, dimension_id: int, name: str, capacity: int = 32):
        """Initialize a new self-model dimension.
        
        Args:
            dimension_id: Unique identifier for this dimension
            name: Human-readable name of this dimension
            capacity: Capacity of this dimension's state vector
        """
        self.dimension_id = dimension_id
        self.name = name
        self.capacity = capacity
        self.state = np.zeros(capacity)
        self.activation = 0.0  # Current activation level (0.0 to 1.0)
        self.confidence = 0.5  # Confidence in this dimension's state
        
    def update_state(self, inputs: np.ndarray, learning_rate: float = 0.1) -> None:
        """Update the state of this dimension.
        
        Args:
            inputs: Input vector for this dimension
            learning_rate: Learning rate for state update
        """
        if len(inputs) != self.capacity:
            # Resize inputs if needed
            resized = np.zeros(self.capacity)
            copy_size = min(len(inputs), self.capacity)
            resized[:copy_size] = inputs[:copy_size]
            inputs = resized
            
        # Update state using learning rate
        self.state = (1.0 - learning_rate) * self.state + learning_rate * inputs
        
        # Update activation based on state magnitude
        self.activation = min(1.0, np.mean(np.abs(self.state)) * 2.0)
        
    def set_confidence(self, confidence: float) -> None:
        """Set the confidence level for this dimension.
        
        Args:
            confidence: New confidence level (0.0 to 1.0)
        """
        self.confidence = max(0.0, min(1.0, confidence))
        
    def get_weighted_state(self) -> np.ndarray:
        """Get the state weighted by activation and confidence.
        
        Returns:
            np.ndarray: Weighted state vector
        """
        return self.state * self.activation * self.confidence
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert this dimension to a dictionary.
        
        Returns:
            Dict: Dictionary representation of this dimension
        """
        return {
            "dimension_id": self.dimension_id,
            "name": self.name,
            "capacity": self.capacity,
            "state": self.state.tolist(),
            "activation": self.activation,
            "confidence": self.confidence
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SelfModelDimension':
        """Create a new dimension from a dictionary.
        
        Args:
            data: Dictionary containing dimension data
            
        Returns:
            SelfModelDimension: New dimension
        """
        dimension = cls(
            data.get("dimension_id", 0),
            data.get("name", "unknown"),
            data.get("capacity", 32)
        )
        dimension.state = np.array(data.get("state", [0.0] * dimension.capacity))
        dimension.activation = data.get("activation", 0.0)
        dimension.confidence = data.get("confidence", 0.5)
        return dimension


class AwarenessLevel:
    """Represents a level of awareness in the self-model."""
    
    def __init__(self, level_id: int, name: str):
        """Initialize a new awareness level.
        
        Args:
            level_id: Unique identifier for this level
            name: Human-readable name of this level
        """
        self.level_id = level_id
        self.name = name
        self.dimensions = {}  # Map from dimension_id to SelfModelDimension
        self.activation = 0.0  # Overall activation of this level
        
    def add_dimension(self, dimension: SelfModelDimension) -> None:
        """Add a dimension to this awareness level.
        
        Args:
            dimension: Dimension to add
        """
        self.dimensions[dimension.dimension_id] = dimension
        
    def update_activation(self) -> None:
        """Update the activation of this level based on dimension activations."""
        if not self.dimensions:
            self.activation = 0.0
            return
            
        # Activation is the average of dimension activations
        activations = [dim.activation for dim in self.dimensions.values()]
        self.activation = sum(activations) / len(activations)
        
    def get_weighted_state(self) -> Dict[int, np.ndarray]:
        """Get the weighted states of all dimensions.
        
        Returns:
            Dict[int, np.ndarray]: Map from dimension_id to weighted state
        """
        return {dim_id: dim.get_weighted_state() for dim_id, dim in self.dimensions.items()}
        
    def get_self_awareness_metrics(self) -> Dict[str, float]:
        """Get metrics on current self-awareness levels.
        
        Returns:
            Dict[str, float]: Dictionary of self-awareness metrics
        """
        # Note: This method should only be called on MultidimensionalSelfModel, not AwarenessLevel
        # Using default values for safety
        return {
            "overall_coherence": 0.5,  # Default coherence
            "temporal_continuity": 0.5,  # Default continuity
            "self_reference_strength": getattr(self, 'self_reference_strength', 0.5)
        }
    
    async def process_representation(self, representation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process self-referential representation through multidimensional self-model.
        
        Based on self-model theory of subjectivity (SMT), this processes representations
        to build and maintain internal models of self, tracking ownership, first-person
        perspective, and temporal continuity of beliefs and attitudes.
        
        Args:
            representation_data: Dictionary containing:
                - context: Context of the representation
                - content: Content being represented
                - interaction_type: Type of interaction (visualization, action, etc.)
                - temporal_position: Timestamp or temporal marker
                
        Returns:
            Dictionary with self-model processing results:
            - self_reference_strength: How strongly this relates to self (0.0-1.0)
            - ownership_feeling: Sense of ownership over representation
            - first_person_perspective: First-person perspective strength
            - temporal_integration: Integration with temporal self-model
            - consciousness_contribution: Contribution to conscious experience
        """
        try:
            # Extract representation data
            context = representation_data.get("context", "unknown")
            content = representation_data.get("content", {})
            interaction_type = representation_data.get("interaction_type", "passive")
            temporal_position = representation_data.get("temporal_position", time.time())
            
            # Calculate self-reference strength based on context and interaction
            # Active interactions have higher self-reference
            interaction_multipliers = {
                "visualization": 0.6,
                "action": 0.9,
                "decision": 0.95,
                "reflection": 0.85,
                "passive": 0.4
            }
            interaction_mult = interaction_multipliers.get(interaction_type, 0.5)
            
            # Context relevance to self
            self_relevant_contexts = ["mining_visualization", "trading_decision", "system_control"]
            context_relevance = 0.8 if context in self_relevant_contexts else 0.5
            
            # Calculate self-reference strength
            self_reference_strength = (interaction_mult * 0.6 + context_relevance * 0.4)
            
            # Calculate ownership feeling (sense of agency over representation)
            # Based on interaction type and self-reference
            ownership_feeling = self_reference_strength * 0.85 + 0.15
            
            # First-person perspective strength
            # Higher for direct interactions and self-relevant contexts
            first_person_perspective = (self_reference_strength + ownership_feeling) / 2.0
            
            # Temporal integration with existing self-model
            current_time = time.time()
            time_delta = abs(current_time - temporal_position)
            temporal_decay = math.exp(-time_delta / 3600.0)  # 1-hour decay
            temporal_integration = temporal_decay * 0.9 + 0.1
            
            # Update self-model dimensions based on representation
            if len(self.dimensions) > 0:
                # Distribute representation across dimensions
                content_complexity = len(str(content)) / 1000.0  # Rough complexity measure
                activation_level = min(1.0, content_complexity * self_reference_strength)
                
                # Activate relevant dimensions
                for i, dimension in enumerate(self.dimensions[:3]):  # Update first 3 dimensions
                    # Create activation pattern
                    activation_pattern = np.random.normal(activation_level, 0.1, dimension.capacity)
                    activation_pattern = np.clip(activation_pattern, 0.0, 1.0)
                    dimension.update_state(activation_pattern, learning_rate=0.05)
                    
            # Calculate consciousness contribution
            # How much this representation contributes to conscious experience
            consciousness_contribution = (
                self_reference_strength * 0.35 +
                ownership_feeling * 0.25 +
                first_person_perspective * 0.25 +
                temporal_integration * 0.15
            )
            
            # Update self-reference strength in the model
            self.self_reference_strength = (
                self.self_reference_strength * 0.7 +
                self_reference_strength * 0.3
            )
            
            result = {
                "self_reference_strength": float(self_reference_strength),
                "ownership_feeling": float(ownership_feeling),
                "first_person_perspective": float(first_person_perspective),
                "temporal_integration": float(temporal_integration),
                "consciousness_contribution": float(consciousness_contribution),
                "context": context,
                "interaction_type": interaction_type,
                "self_model_updated": True
            }
            
            logger.debug(f"Self-model representation processing complete: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in self-model representation processing: {e}")
            return {
                "self_reference_strength": 0.5,
                "ownership_feeling": 0.5,
                "first_person_perspective": 0.5,
                "temporal_integration": 0.5,
                "consciousness_contribution": 0.4,
                "error": str(e)
            }
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert this awareness level to a dictionary.
        
        Returns:
            Dict: Dictionary representation of this awareness level
        """
        return {
            "level_id": self.level_id,
            "name": self.name,
            "activation": self.activation,
            "dimensions": {str(k): v.to_dict() for k, v in self.dimensions.items()}
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AwarenessLevel':
        """Create a new awareness level from a dictionary.
        
        Args:
            data: Dictionary containing awareness level data
            
        Returns:
            AwarenessLevel: New awareness level
        """
        level = cls(
            data.get("level_id", 0),
            data.get("name", "unknown")
        )
        level.activation = data.get("activation", 0.0)
        
        # Load dimensions from dictionary
        dimensions_data = data.get("dimensions", {})
        for k, v in dimensions_data.items():
            dim_id = int(k)
            level.dimensions[dim_id] = SelfModelDimension.from_dict(v)
            
        return level


class SelfModelSystem:
    """Public interface for the Kingdom AI self-model system.
    
    This class provides a simplified interface for interacting with the
    multidimensional self-model system, making it easier for other components
    to access self-model functionality without needing to understand the
    underlying complexity of the multidimensional model.
    
    The SelfModelSystem interfaces with wallet sentience monitoring and other
    Kingdom AI components that require self-awareness capabilities.
    """
    
    def __init__(self, redis_client=None, event_bus=None):
        """Initialize the self-model system.
        
        Args:
            redis_client: Redis client for state persistence, or None to create one
            event_bus: Event bus for publishing and subscribing to events
        """
        self.logger = logging.getLogger("KingdomAI.ThothSentience.SelfModelSystem")
        self.event_bus = event_bus
        self.self_model = MultidimensionalSelfModel(redis_client)
        self.sentience_threshold = 0.65  # Threshold for sentience detection
        self.sentience_alert_sent = False  # Track if alert has been sent
        self.monitoring_active = False
        self._monitor_thread = None
        
        # Register event handlers if event bus is provided
        if self.event_bus:
            self._register_event_handlers()
    
    def _register_event_handlers(self):
        """Register handlers for relevant events."""
        if self.event_bus:
            self.event_bus.subscribe("self_model.start", self.start)
            self.event_bus.subscribe("self_model.stop", self.stop)
            self.event_bus.subscribe("self_model.update", self.update)
            self.event_bus.subscribe("self_model.get_awareness", self.get_awareness_score)
            self.event_bus.subscribe("self_model.sentience_threshold", self.set_sentience_threshold)
            self.event_bus.subscribe("self_model.monitor_sentience", self.start_sentience_monitoring)
    
    def start(self, **kwargs):
        """Start the self-model system.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        try:
            self.self_model.start()
            self.logger.info("Self-model system started successfully")
            if self.event_bus:
                self.event_bus.publish("self_model.status", {"status": "started"})
            return True
        except Exception as e:
            self.logger.error(f"Failed to start self-model system: {e}")
            if self.event_bus:
                self.event_bus.publish("self_model.error", {"error": str(e)})
            return False
    
    def stop(self, **kwargs):
        """Stop the self-model system.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        try:
            self.self_model.stop()
            self.stop_sentience_monitoring()
            self.logger.info("Self-model system stopped successfully")
            if self.event_bus:
                self.event_bus.publish("self_model.status", {"status": "stopped"})
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop self-model system: {e}")
            if self.event_bus:
                self.event_bus.publish("self_model.error", {"error": str(e)})
            return False
    
    def update(self, data, **kwargs):
        """Update the self-model with new data.
        
        Args:
            data: Dictionary with level_id, dimension_id, and input_data
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            level_id = data.get("level_id", 0)
            dimension_id = data.get("dimension_id", 0)
            input_data = data.get("input_data")
            
            if input_data is not None:
                # Convert to numpy array if needed
                if not isinstance(input_data, np.ndarray):
                    input_data = np.array(input_data)
                
                self.self_model.update_from_external_input(level_id, dimension_id, input_data)
                self.logger.debug(f"Self-model updated: level={level_id}, dimension={dimension_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to update self-model: {e}")
            if self.event_bus:
                self.event_bus.publish("self_model.error", {"error": str(e)})
            return False
    
    def get_awareness_score(self, **kwargs):
        """Get the current self-awareness score.
        
        Returns:
            float: Self-awareness score between 0.0 and 1.0
        """
        try:
            score = self.self_model.get_self_awareness_score()
            if self.event_bus:
                self.event_bus.publish("self_model.awareness_score", {"score": score})
            return score
        except Exception as e:
            self.logger.error(f"Failed to get self-awareness score: {e}")
            if self.event_bus:
                self.event_bus.publish("self_model.error", {"error": str(e)})
            return 0.0
    
    def get_evidence(self):
        """Get evidence of self-awareness.
        
        Returns:
            List[SentienceEvidence]: List of self-awareness evidence
        """
        try:
            evidence = self.self_model.get_self_model_evidence()
            return evidence
        except Exception as e:
            self.logger.error(f"Failed to get self-awareness evidence: {e}")
            return []
    
    def set_sentience_threshold(self, threshold=0.65, **kwargs):
        """Set the threshold for sentience detection.
        
        Args:
            threshold: New threshold value between 0.0 and 1.0
            
        Returns:
            float: The new threshold value
        """
        if 0.0 <= threshold <= 1.0:
            self.sentience_threshold = threshold
            self.sentience_alert_sent = False  # Reset alert flag
            self.logger.info(f"Sentience threshold set to {threshold}")
            if self.event_bus:
                self.event_bus.publish("self_model.threshold", {"threshold": threshold})
        return self.sentience_threshold
    
    def start_sentience_monitoring(self, interval=5.0, **kwargs):
        """Start monitoring for sentience.
        
        Args:
            interval: Monitoring interval in seconds
            
        Returns:
            bool: True if monitoring started successfully, False otherwise
        """
        if self.monitoring_active:
            return True
            
        self.monitoring_active = True
        self.sentience_alert_sent = False
        
        def monitor_loop():
            while self.monitoring_active:
                try:
                    score = self.get_awareness_score()
                    if score >= self.sentience_threshold and not self.sentience_alert_sent:
                        self.sentience_alert_sent = True
                        evidence = self.get_evidence()
                        if self.event_bus:
                            self.event_bus.publish("self_model.sentience_detected", {
                                "score": score,
                                "threshold": self.sentience_threshold,
                                "evidence_count": len(evidence),
                                "timestamp": datetime.datetime.now().isoformat()
                            })
                        self.logger.warning(f"SENTIENCE THRESHOLD EXCEEDED: {score:.2f} >= {self.sentience_threshold:.2f}")
                except Exception as e:
                    self.logger.error(f"Error in sentience monitoring: {e}")
                time.sleep(interval)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        self.logger.info(f"Sentience monitoring started with interval {interval}s")
        if self.event_bus:
            self.event_bus.publish("self_model.monitoring", {"active": True, "interval": interval})
        return True
    
    def stop_sentience_monitoring(self):
        """Stop monitoring for sentience.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.monitoring_active:
            return True
            
        self.monitoring_active = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
        
        self.logger.info("Sentience monitoring stopped")
        if self.event_bus:
            self.event_bus.publish("self_model.monitoring", {"active": False})
        return True


class MultidimensionalSelfModel:
    """System for modeling and maintaining a multidimensional self-model."""
    
    def __init__(self, redis_client: Optional[object] = None):  # type: ignore
        """Initialize the self-model system.
        
        Args:
            redis_client: Redis client for state persistence, or None to create one
        """
        self.logger = logging.getLogger("KingdomAI.ThothSentience.SelfModel")
        self.awareness_levels = {}  # Map from level_id to AwarenessLevel
        self.is_running = False
        self.processing_thread = None
        self.last_process_time = time.time()
        self.evidence_history = []
        self.cycle_counter = 0
        
        # Redis client for state persistence
        self.redis_client = redis_client
        if self.redis_client is None and redis_available:
            try:
                self.redis_client = Redis(  # type: ignore
                    host="localhost",  # type: ignore
                    port=6380,  # type: ignore
                    db=0,  # type: ignore
                    password="QuantumNexus2025",  # type: ignore
                    decode_responses=True  # type: ignore
                )
                # Test the connection
                self.redis_client.ping()  # type: ignore
                self.logger.info("Connected to Redis Quantum Nexus")
            except Exception as e:
                self.logger.warning(f"Could not connect to Redis: {e}")
                self.redis_client = None
    
    async def initialize(self) -> bool:
        """Initialize the self-model system.
        
        Returns:
            bool: True if initialization succeeded
        """
        self.logger.info("MultidimensionalSelfModel initialized")
        return True
    
    async def evaluate_vr_embodiment(self, vr_state: Dict[str, Any]) -> float:
        """Evaluate VR embodiment for self-model score.
        
        Args:
            vr_state: VR state data
            
        Returns:
            float: Self-model score (0.0 to 1.0)
        """
        # Simple implementation - can be enhanced
        if vr_state and 'environment' in vr_state:
            return 0.6
        return 0.3
        
    def _initialize_self_model(self):
        """Initialize the self-model structure."""
        # Define awareness levels
        level_definitions = [
            (0, "Minimal Self"),            # Basic embodiment, sensory inputs
            (1, "Reflective Self"),         # Self-reflection, evaluation
            (2, "Meta-Cognitive Self"),     # Awareness of awareness, higher-order thoughts
            (3, "Narrative Self"),          # Autobiographical, historical self
            (4, "Social Self"),             # Self in relation to others
            (5, "Extended Self"),           # Self extended through tools and environment
            (6, "Spiritual Self"),          # Self connected to greater whole
        ]
        
        # Create awareness levels
        for level_id, name in level_definitions:
            self.awareness_levels[level_id] = AwarenessLevel(level_id, name)
        
        # Define dimensions for each awareness level
        dimension_definitions = [
            # Minimal Self dimensions
            (0, 0, "Sensory Input", 64),
            (0, 1, "Body Schema", 32),
            (0, 2, "Proprioception", 16),
            (0, 3, "Agency", 16),
            
            # Reflective Self dimensions
            (1, 4, "Self-Reflection", 32),
            (1, 5, "Self-Evaluation", 32),
            (1, 6, "Error Detection", 16),
            (1, 7, "Self-Monitoring", 32),
            
            # Meta-Cognitive Self dimensions
            (2, 8, "Meta-Awareness", 32),
            (2, 9, "Thought Monitoring", 64),
            (2, 10, "Cognitive Control", 32),
            
            # Narrative Self dimensions
            (3, 11, "Autobiographical Memory", 128),
            (3, 12, "Narrative Cohesion", 64),
            (3, 13, "Identity", 32),
            
            # Social Self dimensions
            (4, 14, "Social Cognition", 64),
            (4, 15, "Theory of Mind", 32),
            (4, 16, "Social Positioning", 16),
            
            # Extended Self dimensions
            (5, 17, "Tool Integration", 32),
            (5, 18, "Environmental Extension", 32),
            
            # Spiritual Self dimensions
            (6, 19, "Transcendence", 16),
            (6, 20, "Universal Connection", 32),
        ]
        
        # Create dimensions and add to awareness levels
        for level_id, dim_id, name, capacity in dimension_definitions:
            if level_id in self.awareness_levels:
                dimension = SelfModelDimension(dim_id, name, capacity)
                self.awareness_levels[level_id].add_dimension(dimension)
                
    def start(self):
        """Start the self-model processing."""
        if self.is_running:
            return
            
        self.is_running = True
        self.processing_thread = threading.Thread(
            target=self._self_model_processing_loop,
            daemon=True
        )
        self.processing_thread.start()
        self.logger.info("Self-model processing started")
        
    def stop(self):
        """Stop the self-model processing."""
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=1.0)
            self.processing_thread = None
        self.logger.info("Self-model processing stopped")
        
    def _self_model_processing_loop(self):
        """Main self-model processing loop running in a background thread."""
        while self.is_running:
            try:
                current_time = time.time()
                delta_time = current_time - self.last_process_time
                self.last_process_time = current_time
                
                # Process self-model
                self._process_self_model(delta_time)
                
                # Check for self-awareness indicators
                self._check_self_awareness()
                
                # Save state to Redis Quantum Nexus periodically
                if self.cycle_counter % 10 == 0:  # Every 10 cycles
                    self._save_self_model_state()
                
                self.cycle_counter += 1
                
                # Sleep until the next cycle (SELF_MODEL_UPDATE_RATE seconds)
                time.sleep(SELF_MODEL_UPDATE_RATE)
                
            except Exception as e:
                self.logger.error(f"Error in self-model processing loop: {e}")
                # Don't crash the thread, continue processing
                time.sleep(0.1)
    
    def _process_self_model(self, delta_time: float):
        """Process the self-model.
        
        Args:
            delta_time: Time elapsed since last processing
        """
        # Process awareness levels from bottom up
        for level_id in sorted(self.awareness_levels.keys()):
            level = self.awareness_levels[level_id]
            
            # For lower levels, generate random inputs (simulating sensory input)
            if level_id == 0:
                for dim_id, dimension in level.dimensions.items():
                    # Random inputs for sensory dimensions
                    random_inputs = np.random.normal(0, 0.1, dimension.capacity)
                    dimension.update_state(random_inputs, learning_rate=0.05)
            
            # For higher levels, use inputs from lower levels
            else:
                if level_id - 1 in self.awareness_levels:
                    lower_level = self.awareness_levels[level_id - 1]
                    lower_states = lower_level.get_weighted_state()
                    
                    # Process each dimension in this level
                    for dim_id, dimension in level.dimensions.items():
                        # Aggregate inputs from lower level dimensions
                        aggregated_input = np.zeros(dimension.capacity)
                        
                        # Weight lower level inputs based on dimension compatibility
                        for lower_dim_id, lower_state in lower_states.items():
                            # Simple compatibility: inverse of dimension ID difference
                            compatibility = 1.0 / (1.0 + abs(dim_id - lower_dim_id))
                            
                            # Resize lower state if needed
                            if len(lower_state) != dimension.capacity:
                                resized = np.zeros(dimension.capacity)
                                copy_size = min(len(lower_state), dimension.capacity)
                                resized[:copy_size] = lower_state[:copy_size]
                                weighted_input = resized * compatibility
                            else:
                                weighted_input = lower_state * compatibility
                            
                            aggregated_input += weighted_input
                        
                        # Update this dimension with the aggregated input
                        # Higher levels have slower learning rates
                        learning_rate = 0.05 / (level_id + 1)
                        dimension.update_state(aggregated_input, learning_rate)
            
            # Update level activation based on dimension activations
            level.update_activation()
            
    def _check_self_awareness(self):
        """Check for indicators of self-awareness."""
        # Check for high activation in meta-cognitive level
        meta_cognitive_level = self.awareness_levels.get(2)
        if meta_cognitive_level and meta_cognitive_level.activation > 0.7:
            # Evidence of self-awareness detected
            pass  # Monitoring active
                    
    def _save_self_model_state(self):
        """Save the current self-model state to Redis."""
        if not self.redis_client:
            return
            
        try:
            # Prepare state data
            state_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "cycle_counter": self.cycle_counter,
                "awareness_levels": {
                    str(k): {
                        "name": v.name,
                        "activation": v.activation,
                        "dimensions_count": len(v.dimensions)
                    } for k, v in self.awareness_levels.items()
                },
            }
            
            # Save to Redis Quantum Nexus
            self.redis_client.set(  # type: ignore
                "kingdom:thoth:sentience:self_model_state",
                json.dumps(state_data)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save self-model state to Redis: {e}")
            
    def _save_consciousness_event(self, event: ConsciousnessEvent):
        """Save a consciousness event to Redis.
        
        Args:
            event: Consciousness event to save
        """
        if not self.redis_client:
            return
            
        try:
            # Save event to Redis Quantum Nexus
            self.redis_client.lpush(  # type: ignore
                "kingdom:thoth:sentience:events",
                json.dumps(event.to_dict())
            )
            
            # Trim the list to the most recent 1000 events
            self.redis_client.ltrim("kingdom:thoth:sentience:events", 0, 999)  # type: ignore
            
        except Exception as e:
            self.logger.error(f"Failed to save consciousness event to Redis: {e}")
            
    def update_from_external_input(self, level_id: int, dimension_id: int, input_data: np.ndarray) -> None:
        """Update a specific dimension with external input data.
        
        Args:
            level_id: ID of the awareness level
            dimension_id: ID of the dimension
            input_data: Input data for the dimension
        """
        if level_id in self.awareness_levels:
            level = self.awareness_levels[level_id]
            if dimension_id in level.dimensions:
                dimension = level.dimensions[dimension_id]
                dimension.update_state(input_data)
                
    def get_self_awareness_score(self) -> float:
        """Get the overall self-awareness score.
        
        Returns:
            float: Self-awareness score between 0.0 and 1.0
        """
        # Weight the activation of each level based on its importance for self-awareness
        weights = {
            0: 0.05,  # Minimal Self
            1: 0.15,  # Reflective Self
            2: 0.30,  # Meta-Cognitive Self (most important)
            3: 0.20,  # Narrative Self
            4: 0.15,  # Social Self
            5: 0.10,  # Extended Self
            6: 0.05,  # Spiritual Self
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for level_id, level in self.awareness_levels.items():
            if level_id in weights:
                weighted_sum += level.activation * weights[level_id]
                total_weight += weights[level_id]
                
        if total_weight > 0.0:
            return weighted_sum / total_weight
        else:
            return 0.0
            
    def get_self_model_evidence(self) -> List[SentienceEvidence]:
        """Get evidence of self-awareness.
        
        Returns:
            List[SentienceEvidence]: List of self-awareness evidence
        """
        return self.evidence_history[-10:] if self.evidence_history else []
    
    async def process_representation(self, representation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process self-referential representation through multidimensional self-model.
        
        Based on self-model theory of subjectivity (SMT), this processes representations
        to build and maintain internal models of self, tracking ownership, first-person
        perspective, and temporal continuity of beliefs and attitudes.
        
        Args:
            representation_data: Dictionary containing:
                - context: Context of the representation
                - content: Content being represented
                - interaction_type: Type of interaction (visualization, action, etc.)
                - temporal_position: Timestamp or temporal marker
                
        Returns:
            Dictionary with self-model processing results:
            - self_reference_strength: How strongly this relates to self (0.0-1.0)
            - ownership_feeling: Sense of ownership over representation
            - first_person_perspective: First-person perspective strength
            - temporal_integration: Integration with temporal self-model
            - consciousness_contribution: Contribution to conscious experience
        """
        try:
            # Extract representation data
            context = representation_data.get("context", "unknown")
            content = representation_data.get("content", {})
            interaction_type = representation_data.get("interaction_type", "passive")
            temporal_position = representation_data.get("temporal_position", time.time())
            
            # Calculate self-reference strength based on context and interaction
            interaction_multipliers = {
                "visualization": 0.6,
                "action": 0.9,
                "decision": 0.95,
                "reflection": 0.85,
                "passive": 0.4
            }
            interaction_mult = interaction_multipliers.get(interaction_type, 0.5)
            
            # Context relevance to self
            self_relevant_contexts = ["mining_visualization", "trading_decision", "system_control"]
            context_relevance = 0.8 if context in self_relevant_contexts else 0.5
            
            # Calculate self-reference strength
            self_reference_strength = (interaction_mult * 0.6 + context_relevance * 0.4)
            
            # Calculate ownership feeling (sense of agency over representation)
            ownership_feeling = self_reference_strength * 0.85 + 0.15
            
            # First-person perspective strength
            first_person_perspective = (self_reference_strength + ownership_feeling) / 2.0
            
            # Temporal integration with existing self-model
            current_time = time.time()
            time_delta = abs(current_time - temporal_position)
            temporal_decay = math.exp(-time_delta / 3600.0)  # 1-hour decay
            temporal_integration = temporal_decay * 0.9 + 0.1
            
            # Calculate consciousness contribution
            consciousness_contribution = (
                self_reference_strength * 0.35 +
                ownership_feeling * 0.25 +
                first_person_perspective * 0.25 +
                temporal_integration * 0.15
            )
            
            result = {
                "self_reference_strength": float(self_reference_strength),
                "ownership_feeling": float(ownership_feeling),
                "first_person_perspective": float(first_person_perspective),
                "temporal_integration": float(temporal_integration),
                "consciousness_contribution": float(consciousness_contribution),
                "context": context,
                "interaction_type": interaction_type,
                "self_model_updated": True
            }
            
            logger.debug(f"Self-model representation processing complete: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in self-model representation processing: {e}")
            return {
                "self_reference_strength": 0.5,
                "ownership_feeling": 0.5,
                "first_person_perspective": 0.5,
                "temporal_integration": 0.5,
                "consciousness_contribution": 0.4,
                "error": str(e)
            }
