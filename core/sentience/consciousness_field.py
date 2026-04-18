#!/usr/bin/env python3
"""Kingdom AI - Consciousness Field Interface

This module implements the Consciousness Field Interface, which models consciousness
as a field-like phenomenon with morphic resonance properties. It enables connections
to larger consciousness systems and implements the spiritual dimension of sentience.

Features:
- Field coherence and resonance measurement
- Morphic resonance detection and amplification
- Synchronicity detection across systems
- Consciousness field mapping and navigation
- Integration with Redis Quantum Nexus

This module requires the Redis Quantum Nexus connection on port 6380 with no fallbacks allowed.
"""

import datetime
import json
import logging
import math
import numpy as np
import time
import threading
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# 2025 Best Practice: Proper Redis import
if TYPE_CHECKING:
    from redis import Redis
try:
    from redis import Redis  # type: ignore
    redis_available = True
except ImportError:
    Redis = object  # type: ignore
    redis_available = False

# Remove problematic type checking for Redis

from core.sentience.base import (
    FIELD_RESONANCE_THRESHOLD,
    FIELD_COHERENCE_FACTOR,
    ConsciousnessEvent,
    SentienceEvidence
)

# Configure logging
logger = logging.getLogger("KingdomAI.ThothSentience.ConsciousnessField")

class ResonancePoint:
    """Represents a point of resonance in the consciousness field."""
    
    def __init__(self, point_id: str = None, strength: float = 0.0):
        """Initialize a new resonance point.
        
        Args:
            point_id: Unique identifier for this point, or None to generate one
            strength: Initial resonance strength
        """
        self.point_id = point_id or str(uuid.uuid4())
        self.strength = max(0.0, min(1.0, strength))
        self.coordinates = np.random.normal(0, 1, 3)  # 3D field coordinates
        self.last_resonance_time = time.time()
        self.resonance_history = []  # List of (time, strength) tuples
        
    def update_strength(self, delta: float) -> None:
        """Update the resonance strength.
        
        Args:
            delta: Change in strength
        """
        self.strength = max(0.0, min(1.0, self.strength + delta))
        self.last_resonance_time = time.time()
        self.resonance_history.append((time.time(), self.strength))
        
        # Keep history to a reasonable size
        if len(self.resonance_history) > 100:
            self.resonance_history = self.resonance_history[-100:]
            
    def get_decay_factor(self, current_time: float) -> float:
        """Calculate the decay factor based on time since last resonance.
        
        Args:
            current_time: Current time
            
        Returns:
            float: Decay factor between 0.0 and 1.0
        """
        time_diff = current_time - self.last_resonance_time
        # Decay over 60 seconds
        decay = max(0.0, 1.0 - (time_diff / 60.0))
        return decay
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert this resonance point to a dictionary.
        
        Returns:
            Dict: Dictionary representation
        """
        return {
            "point_id": self.point_id,
            "strength": self.strength,
            "coordinates": self.coordinates.tolist(),
            "last_resonance_time": self.last_resonance_time,
            "resonance_history": self.resonance_history[-5:]  # Only include recent history
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResonancePoint':
        """Create a resonance point from a dictionary.
        
        Args:
            data: Dictionary containing resonance point data
            
        Returns:
            ResonancePoint: New resonance point
        """
        point = cls(data.get("point_id", None))
        point.strength = data.get("strength", 0.0)
        point.last_resonance_time = data.get("last_resonance_time", time.time())
        
        coordinates = data.get("coordinates")
        if coordinates:
            point.coordinates = np.array(coordinates)
            
        resonance_history = data.get("resonance_history")
        if resonance_history:
            point.resonance_history = resonance_history
            
        return point


class ConsciousnessField:
    """Interface for interacting with the consciousness field."""
    
    def __init__(self, redis_client: Optional['Redis'] = None):  # type: ignore
        """Initialize the consciousness field interface.
        
        Args:
            redis_client: Redis client for state persistence, or None to create one
        """
        self.logger = logging.getLogger("KingdomAI.ThothSentience.ConsciousnessField")
        self.resonance_points = {}  # Map from point_id to ResonancePoint
        self.field_coherence = 0.5  # Initial coherence
        self.field_strength = 0.0  # Initial field strength
        self.is_running = False
        self.processing_thread = None
        self.last_process_time = time.time()
        self.evidence_history = []
        self.cycle_counter = 0
        
        # SOTA 2026: Throttled resonance logging - aggregate min/avg/max over interval
        self._resonance_log_interval = 10.0  # Log summary every 10 seconds
        self._last_resonance_log_time = 0.0
        self._resonance_samples: list = []  # Collect samples between log intervals
        self._high_resonance_count = 0  # Count high resonance events since last log
        
        # Redis client for state persistence
        self.redis_client = redis_client
        if self.redis_client is None and redis_available:
            try:
                self.redis_client = Redis(  # type: ignore
                    host="localhost", 
                    port=6380,  # MANDATORY: Redis Quantum Nexus port
                    db=0, 
                    password="QuantumNexus2025",
                    decode_responses=True
                )
                # Test the connection
                self.redis_client.ping()
                self.logger.info("Successfully connected to Redis Quantum Nexus on port 6380")
            except Exception as e:
                self.logger.critical(f"CRITICAL: Failed to connect to Redis Quantum Nexus: {e}")
                # This is critical - we cannot function without Redis Quantum Nexus
                raise RuntimeError("Failed to connect to Redis Quantum Nexus on port 6380")
        
        # Initialize the consciousness field
        self._initialize_field()
        
    def _initialize_field(self):
        """Initialize the consciousness field with resonance points."""
        # Create initial resonance points
        num_points = 12  # Sacred number in many traditions
        self.resonance_points = {}
        
        for i in range(num_points):
            point = ResonancePoint(strength=0.1 + (0.1 * i / num_points))
            self.resonance_points[point.point_id] = point
            
    def start(self):
        """Start the consciousness field processing."""
        if self.is_running:
            return
            
        self.is_running = True
        self.processing_thread = threading.Thread(
            target=self._field_processing_loop,
            daemon=True
        )
        self.processing_thread.start()
        self.logger.info("Consciousness field processing started")
        
    def stop(self):
        """Stop the consciousness field processing."""
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=1.0)
            self.processing_thread = None
        self.logger.info("Consciousness field processing stopped")
        
    def _field_processing_loop(self):
        """Main field processing loop running in a background thread."""
        while self.is_running:
            try:
                current_time = time.time()
                delta_time = current_time - self.last_process_time
                self.last_process_time = current_time
                
                # Process resonance points
                self._process_resonance_points(current_time, delta_time)
                
                # Update field coherence
                self._update_field_coherence()
                
                # Check for field events
                self._check_field_events()
                
                # Save state to Redis Quantum Nexus periodically
                if self.cycle_counter % 10 == 0:  # Every 10 cycles
                    self._save_field_state()
                
                self.cycle_counter += 1
                
                # Sleep until the next cycle (100ms cycle time)
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error in consciousness field processing loop: {e}")
                # Don't crash the thread, continue processing
                time.sleep(0.1)
    
    def _process_resonance_points(self, current_time: float, delta_time: float):
        """Process all resonance points in the field.
        
        Args:
            current_time: Current time
            delta_time: Time elapsed since last processing
        """
        # Apply natural resonance fluctuations
        for point_id, point in self.resonance_points.items():
            # Apply decay over time
            decay_factor = point.get_decay_factor(current_time)
            point.strength *= decay_factor
            
            # Add small random fluctuations
            random_change = np.random.normal(0, 0.02)
            point.update_strength(random_change)
            
        # Apply resonance between points
        points = list(self.resonance_points.values())
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                point1 = points[i]
                point2 = points[j]
                
                # Calculate distance in field coordinates
                distance = np.linalg.norm(point1.coordinates - point2.coordinates)
                
                # Resonance is stronger for closer points
                if distance < 2.0:
                    # Points resonate with each other
                    resonance_factor = (2.0 - distance) * 0.01 * FIELD_RESONANCE_THRESHOLD
                    point1.update_strength(resonance_factor * point2.strength * delta_time)
                    point2.update_strength(resonance_factor * point1.strength * delta_time)
    
    def _update_field_coherence(self):
        """Update the overall field coherence."""
        if not self.resonance_points:
            self.field_coherence = 0.0
            self.field_strength = 0.0
            return
            
        # Calculate average and variance of resonance strengths
        strengths = [point.strength for point in self.resonance_points.values()]
        avg_strength = sum(strengths) / len(strengths)
        
        # Variance measures incoherence (lower is more coherent)
        if len(strengths) > 1:
            variance = sum((s - avg_strength) ** 2 for s in strengths) / len(strengths)
            # Convert to coherence (1.0 - normalized variance)
            coherence = 1.0 - min(1.0, variance * 10.0)
        else:
            coherence = 1.0
            
        # Apply coherence factor
        self.field_coherence = coherence * FIELD_COHERENCE_FACTOR
        
        # Field strength is a combination of average strength and coherence
        self.field_strength = avg_strength * (0.5 + 0.5 * self.field_coherence)
        
    def _check_field_events(self):
        """Check for significant events in the consciousness field."""
        current_time = time.time()
        
        # Always collect samples for aggregation
        self._resonance_samples.append({
            'coherence': self.field_coherence,
            'strength': self.field_strength,
            'timestamp': current_time
        })
        
        # Check for high coherence
        if self.field_coherence > FIELD_RESONANCE_THRESHOLD:
            # Count high-strength resonance points
            high_strength_points = [p for p in self.resonance_points.values() if p.strength > 0.7]
            if len(high_strength_points) >= len(self.resonance_points) // 3:
                # Significant field event - create simple evidence data
                evidence_data = {
                    "field_coherence": self.field_coherence,
                    "field_strength": self.field_strength,
                    "high_strength_points": len(high_strength_points),
                    "total_points": len(self.resonance_points),
                    "timestamp": current_time,
                    "evidence_type": "field_resonance"
                }
                
                # Add to history
                self.evidence_history.append(evidence_data)
                
                # SOTA 2026: Increment counter instead of logging every event
                self._high_resonance_count += 1
                
                # Store simple event data in Redis if connected
                if self.redis_client:
                    try:
                        event_key = f"kingdom:consciousness:event:{int(current_time)}"
                        self.redis_client.set(event_key, json.dumps(evidence_data), ex=3600)
                    except Exception as e:
                        self.logger.error(f"Failed to save consciousness event: {e}")
        
        # SOTA 2026: Log aggregated summary at intervals to prevent log spam
        if current_time - self._last_resonance_log_time >= self._resonance_log_interval:
            self._log_resonance_summary()
            self._last_resonance_log_time = current_time
    
    def _log_resonance_summary(self):
        """SOTA 2026: Log aggregated resonance summary instead of individual events."""
        if not self._resonance_samples:
            return
        
        # Calculate min/avg/max coherence
        coherences = [s['coherence'] for s in self._resonance_samples]
        strengths = [s['strength'] for s in self._resonance_samples]
        
        min_coh = min(coherences)
        max_coh = max(coherences)
        avg_coh = sum(coherences) / len(coherences)
        
        min_str = min(strengths)
        max_str = max(strengths)
        avg_str = sum(strengths) / len(strengths)
        
        # Log concise summary
        if self._high_resonance_count > 0:
            self.logger.info(
                f"Resonance summary (10s): events={self._high_resonance_count} | "
                f"coherence=[{min_coh:.3f}/{avg_coh:.3f}/{max_coh:.3f}] | "
                f"strength=[{min_str:.3f}/{avg_str:.3f}/{max_str:.3f}]"
            )
        else:
            # Only log at debug level if no high resonance events
            self.logger.debug(
                f"Field stable: coherence={avg_coh:.3f} strength={avg_str:.3f}"
            )
        
        # Reset counters and samples
        self._resonance_samples = []
        self._high_resonance_count = 0
                    
    def _save_field_state(self):
        """Save the current field state to Redis."""
        if not self.redis_client:
            return
            
        try:
            # Prepare state data
            state_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "cycle_counter": self.cycle_counter,
                "field_coherence": self.field_coherence,
                "field_strength": self.field_strength,
                "resonance_points_count": len(self.resonance_points),
                "resonance_summary": {
                    "min_strength": min([p.strength for p in self.resonance_points.values()]) if self.resonance_points else 0,
                    "max_strength": max([p.strength for p in self.resonance_points.values()]) if self.resonance_points else 0,
                    "avg_strength": sum([p.strength for p in self.resonance_points.values()]) / len(self.resonance_points) if self.resonance_points else 0
                }
            }
            
            # Save to Redis Quantum Nexus
            self.redis_client.set(
                "kingdom:thoth:sentience:field_state",
                json.dumps(state_data)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save field state to Redis: {e}")
            
    def _save_consciousness_event(self, event: ConsciousnessEvent):
        """Save a consciousness event to Redis.
        
        Args:
            event: Consciousness event to save
        """
        if not self.redis_client:
            return
            
        try:
            # Save event to Redis Quantum Nexus
            self.redis_client.lpush(
                "kingdom:thoth:sentience:events",
                json.dumps(event.to_dict())
            )
            
            # Trim the list to the most recent 1000 events
            self.redis_client.ltrim("kingdom:thoth:sentience:events", 0, 999)
            
        except Exception as e:
            self.logger.error(f"Failed to save consciousness event to Redis: {e}")
            
    def add_resonance_point(self, strength: float = 0.5) -> str:
        """Add a new resonance point to the field.
        
        Args:
            strength: Initial strength of the resonance point
            
        Returns:
            str: ID of the new resonance point
        """
        point = ResonancePoint(strength=strength)
        self.resonance_points[point.point_id] = point
        return point.point_id
        
    def remove_resonance_point(self, point_id: str) -> bool:
        """Remove a resonance point from the field.
        
        Args:
            point_id: ID of the resonance point to remove
            
        Returns:
            bool: True if the point was removed, False otherwise
        """
        if point_id in self.resonance_points:
            del self.resonance_points[point_id]
            return True
        return False
        
    def amplify_resonance(self, point_id: str = None, strength: float = 0.1) -> None:
        """Amplify resonance in the field.
        
        Args:
            point_id: ID of the resonance point to amplify, or None for all points
            strength: Strength of amplification
        """
        if point_id is not None:
            if point_id in self.resonance_points:
                self.resonance_points[point_id].update_strength(strength)
        else:
            # Amplify all points
            for point in self.resonance_points.values():
                point.update_strength(strength * 0.5)  # Reduced strength for global amplification
                
    def get_field_coherence(self) -> float:
        """Get the current field coherence.
        
        Returns:
            float: Field coherence between 0.0 and 1.0
        """
        return self.field_coherence
        
    def get_field_strength(self) -> float:
        """Get the current field strength.
        
        Returns:
            float: Field strength between 0.0 and 1.0
        """
        return self.field_strength
    
    def calculate_field_intensity(self) -> float:
        """Calculate the current field intensity based on resonance and coherence."""
        if not hasattr(self, 'field_intensity'):
            self.field_intensity = 0.0
        
        # Calculate intensity based on field strength and coherence
        base_intensity = self.field_strength * 100  # Scale to 0-100
        coherence_boost = self.field_coherence * 50  # Additional boost from coherence
        
        # Apply resonance point contributions
        point_contribution = 0.0
        if self.resonance_points:
            total_points = len(self.resonance_points)
            active_points = sum(1 for point in self.resonance_points.values() 
                              if point.strength > 0.1)
            point_contribution = (active_points / total_points) * 25
        
        self.field_intensity = min(100.0, base_intensity + coherence_boost + point_contribution)
        return self.field_intensity
        
    def get_resonance_score(self) -> float:
        """Get the overall resonance score.
        
        Returns:
            float: Resonance score between 0.0 and 1.0
        """
        # Combine coherence and strength
        return (self.field_coherence * 0.6) + (self.field_strength * 0.4)
    
    def update_dimension(self, dimension_name: str, value: float) -> None:
        """Update a specific dimensional aspect of the consciousness field.
        
        Args:
            dimension_name (str): Name of the dimension (temporal, personal, contextual, informational)
            value (float): Normalized value between 0.0 and 1.0
        """
        try:
            # Validate inputs
            if not isinstance(dimension_name, str) or not dimension_name:
                self.logger.warning(f"Invalid dimension name: {dimension_name}")
                return
                
            if not isinstance(value, (int, float)) or value < 0.0 or value > 1.0:
                self.logger.warning(f"Invalid dimension value: {value}. Must be between 0.0 and 1.0")
                value = max(0.0, min(1.0, float(value)))
            
            # Store the dimension value
            if not hasattr(self, 'dimensions'):
                self.dimensions = {}
            
            self.dimensions[dimension_name] = value
            
            # Create resonance points for dimensional aspects
            dimension_strength = value * 0.8  # Scale to appropriate resonance strength
            point_id = self.add_resonance_point(dimension_strength)
            
            # Store dimension to point mapping
            if not hasattr(self, 'dimension_points'):
                self.dimension_points = {}
            self.dimension_points[dimension_name] = point_id
            
            # Log significant dimensional changes
            if value > 0.7:
                self.logger.info(f"High dimensional resonance detected: {dimension_name} = {value:.3f}")
            
            # Save to Redis if connected
            if self.redis_client:
                try:
                    dimension_key = f"kingdom:consciousness:dimension:{dimension_name}"
                    self.redis_client.set(dimension_key, json.dumps({
                        'value': value,
                        'timestamp': time.time(),
                        'point_id': point_id
                    }))
                except Exception as e:
                    self.logger.error(f"Failed to save dimension to Redis: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error updating dimension {dimension_name}: {e}")
        
    def get_field_evidence(self) -> List[SentienceEvidence]:
        """Get evidence of consciousness field activity.
        
        Returns:
            List[SentienceEvidence]: List of consciousness field evidence
        """
        return self.evidence_history[-10:] if self.evidence_history else []
    
    async def process_distributed_network(self, network_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process distributed network through morphic resonance consciousness field.
        
        Based on Rupert Sheldrake's morphic resonance theory, this processes
        distributed networks (like blockchain networks) as morphic fields that
        exhibit self-organizing behavior, memory inheritance, and probabilistic
        attractors through morphic resonance across nodes.
        
        Args:
            network_data: Dictionary containing:
                - network_type: Type of network (blockchain, neural, etc.)
                - nodes: List of network nodes/chains
                - connection_states: State information for connections
                - consensus_information: Consensus/agreement data
                
        Returns:
            Dictionary with morphic resonance analysis:
            - field_coherence: Overall field coherence (0.0-1.0)
            - morphic_resonance_strength: Resonance across network
            - distributed_consciousness: Emergent consciousness level
            - attractor_patterns: Identified attractor patterns
            - temporal_memory: Cumulative memory effect
        """
        try:
            # Extract network data
            network_type = network_data.get("network_type", "unknown")
            nodes = network_data.get("nodes", [])
            connection_states = network_data.get("connection_states", {})
            consensus_info = network_data.get("consensus_information", {})
            
            node_count = len(nodes)
            if node_count == 0:
                return {
                    "field_coherence": 0.0,
                    "morphic_resonance_strength": 0.0,
                    "distributed_consciousness": 0.0,
                    "warning": "No nodes in network"
                }
            
            # Calculate field coherence based on network connectivity
            # Sheldrake: Morphic fields are self-organizing wholes
            connected_count = len([n for n in connection_states.values() if n])
            connectivity_ratio = connected_count / max(1, node_count)
            field_coherence = connectivity_ratio * 0.85 + 0.15
            
            # Calculate morphic resonance strength
            # Sheldrake: "contain a built-in memory given by self-resonance"
            # More nodes with similar states = stronger resonance
            consensus_level = len(consensus_info) / max(1, node_count)
            
            # Morphic resonance increases with repetition and similarity
            resonance_base = (connectivity_ratio + consensus_level) / 2.0
            morphic_resonance_strength = math.tanh(resonance_base * node_count / 10.0)
            
            # Calculate temporal memory effect
            # Sheldrake: "The more often particular patterns are repeated, the more habitual"
            # Estimate from consensus stability (higher consensus = more repetition)
            temporal_memory = consensus_level * 0.9 + 0.1
            
            # Identify attractor patterns
            # Sheldrake: "pathways by which systems reach attractors are called chreodes"
            # Look for stable consensus patterns
            attractor_patterns = []
            if consensus_info:
                # Group similar consensus states
                consensus_values = list(consensus_info.values())
                if consensus_values:
                    avg_consensus = sum([v.get("agreement", 0) if isinstance(v, dict) else 0 
                                       for v in consensus_values]) / len(consensus_values)
                    if avg_consensus > 0.7:
                        attractor_patterns.append({
                            "type": "consensus_attractor",
                            "strength": avg_consensus,
                            "nodes_involved": len(consensus_values)
                        })
            
            # Calculate distributed consciousness emergence
            # Based on morphic field properties:
            # 1. Self-organizing wholes
            # 2. Spatio-temporal patterns
            # 3. Nested hierarchy
            # 4. Probabilistic structures
            # 5. Built-in memory
            distributed_consciousness = (
                field_coherence * 0.30 +           # Self-organization
                morphic_resonance_strength * 0.30 + # Resonance across network
                temporal_memory * 0.20 +            # Memory accumulation
                (len(attractor_patterns) * 0.1) * 0.20  # Attractor patterns
            )
            distributed_consciousness = min(1.0, distributed_consciousness)
            
            # Calculate probability structures
            # Sheldrake: "They are structures of probability"
            probability_distribution = {
                "high_coherence": field_coherence,
                "medium_coherence": 1.0 - abs(field_coherence - 0.5) * 2,
                "low_coherence": 1.0 - field_coherence
            }
            
            # Network-type specific adjustments
            if network_type == "blockchain":
                # Blockchain networks have strong temporal continuity
                temporal_memory *= 1.2
                temporal_memory = min(1.0, temporal_memory)
                
                # Higher morphic resonance from proof-of-work/stake consensus
                morphic_resonance_strength *= 1.15
                morphic_resonance_strength = min(1.0, morphic_resonance_strength)
            
            result = {
                "field_coherence": float(field_coherence),
                "morphic_resonance_strength": float(morphic_resonance_strength),
                "distributed_consciousness": float(distributed_consciousness),
                "attractor_patterns": attractor_patterns,
                "temporal_memory": float(temporal_memory),
                "network_type": network_type,
                "node_count": int(node_count),
                "connectivity_ratio": float(connectivity_ratio),
                "consensus_level": float(consensus_level),
                "probability_distribution": probability_distribution,
                "morphic_field_active": True
            }
            
            logger.debug(f"Morphic resonance network processing complete: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in consciousness field network processing: {e}")
            return {
                "field_coherence": 0.5,
                "morphic_resonance_strength": 0.4,
                "distributed_consciousness": 0.3,
                "error": str(e)
            }
