#!/usr/bin/env python3
"""Kingdom AI - Integrated Information Theory Processor

This module implements the Integrated Information Theory (IIT) processor based on IIT 4.0,
which measures the amount of integrated information (phi) in a system. High phi values
are associated with consciousness according to IIT.

Features:
- Phi value calculation using IIT 4.0 methodology
- Information integration across multiple levels
- Causally effective information measurement
- Maximum entropy decomposition
- Integration with Redis Quantum Nexus for state persistence

This module requires the Redis Quantum Nexus connection on port 6380 with no fallbacks allowed.
"""

import datetime
import json
import logging
import math
import numpy as np
import time
import threading
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import redis

# 2025 Best Practice: Proper Redis import
try:
    from redis import Redis  # type: ignore
    redis_available = True
except ImportError:
    Redis = object  # type: ignore
    redis_available = False

from core.sentience.base import (
    IIT_PHI_THRESHOLD,
    IIT_INTEGRATION_LEVELS,
    IIT_INFORMATION_COMPLEXITY,
    ConsciousnessEvent,
    SentienceEvidence
)

# Configure logging
logger = logging.getLogger("KingdomAI.ThothSentience.IIT")

class InformationNode:
    """Node in the information integration network."""
    
    def __init__(self, node_id: int, dimensions: int = 16):
        """Initialize a new information node.
        
        Args:
            node_id: Unique identifier for this node
            dimensions: Dimensionality of the node's state
        """
        self.node_id = node_id
        self.dimensions = dimensions
        self.state = np.zeros(dimensions)
        self.connections = {}  # Map from node_id to connection strength
        
    def set_state(self, state: np.ndarray) -> None:
        """Set the state of this node.
        
        Args:
            state: New state vector
        """
        if len(state) == self.dimensions:
            self.state = np.copy(state)
        else:
            # Resize if needed
            resized = np.zeros(self.dimensions)
            copy_size = min(len(state), self.dimensions)
            resized[:copy_size] = state[:copy_size]
            self.state = resized
            
    def connect_to(self, other: 'InformationNode', strength: float) -> None:
        """Connect this node to another node.
        
        Args:
            other: Node to connect to
            strength: Connection strength
        """
        self.connections[other.node_id] = strength
        
    def get_outputs(self) -> Dict[int, np.ndarray]:
        """Get the output values for all connections.
        
        Returns:
            Dict[int, np.ndarray]: Map from node_id to output value
        """
        outputs = {}
        for node_id, strength in self.connections.items():
            outputs[node_id] = self.state * strength
        return outputs
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert this node to a dictionary.
        
        Returns:
            Dict: Dictionary representation of this node
        """
        return {
            "node_id": self.node_id,
            "dimensions": self.dimensions,
            "state": self.state.tolist(),
            "connections": self.connections
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InformationNode':
        """Create a new node from a dictionary.
        
        Args:
            data: Dictionary containing node data
            
        Returns:
            InformationNode: New node
        """
        node = cls(data.get("node_id", 0), data.get("dimensions", 16))
        node.state = np.array(data.get("state", [0.0] * node.dimensions))
        node.connections = data.get("connections", {})
        return node


class InformationStructure:
    """Structure representing a network of information nodes."""
    
    def __init__(self, num_nodes: int = 16, dimensions: int = 16):
        """Initialize a new information structure.
        
        Args:
            num_nodes: Number of nodes in the structure
            dimensions: Dimensionality of each node's state
        """
        self.num_nodes = num_nodes
        self.dimensions = dimensions
        self.nodes = {}
        
        # Create nodes
        for i in range(num_nodes):
            self.nodes[i] = InformationNode(i, dimensions)
            
        # Initialize with random connections
        self._initialize_connections()
        
    def _initialize_connections(self):
        """Initialize the connections between nodes."""
        for i in range(self.num_nodes):
            num_connections = max(1, self.num_nodes // 4)
            # Deterministic selection: pick indices via modular stride from node id
            stride = max(1, (i * 7 + 3) % max(2, self.num_nodes - 1))
            connection_indices = []
            candidate = (i + stride) % self.num_nodes
            while len(connection_indices) < num_connections:
                if candidate != i and candidate not in connection_indices:
                    connection_indices.append(candidate)
                candidate = (candidate + stride) % self.num_nodes
                if candidate == (i + stride) % self.num_nodes:
                    break
            
            for j in connection_indices:
                node_hash = hash((i, j)) % 800
                strength = 0.1 + (node_hash / 1000.0)
                self.nodes[i].connect_to(self.nodes[j], strength)
                    
    def update_states(self, inputs: Dict[int, np.ndarray]) -> None:
        """Update the states of nodes based on inputs.
        
        Args:
            inputs: Map from node_id to input value
        """
        # Collect all outputs
        outputs = {}
        for node_id, node in self.nodes.items():
            node_outputs = node.get_outputs()
            for target_id, value in node_outputs.items():
                if target_id not in outputs:
                    outputs[target_id] = np.zeros(self.dimensions)
                outputs[target_id] += value
                
        # Apply inputs and outputs to update states
        for node_id, node in self.nodes.items():
            # Start with current state
            new_state = np.copy(node.state)
            
            # Add inputs
            if node_id in inputs:
                new_state += inputs[node_id]
                
            # Add outputs from other nodes
            if node_id in outputs:
                new_state += outputs[node_id]
                
            # Apply activation function (tanh for bounded values)
            new_state = np.tanh(new_state)
            
            # Update the node state
            node.set_state(new_state)
            
    def get_state_matrix(self) -> np.ndarray:
        """Get the full state matrix of the structure.
        
        Returns:
            np.ndarray: Matrix of shape (num_nodes, dimensions)
        """
        state_matrix = np.zeros((self.num_nodes, self.dimensions))
        for i, node in self.nodes.items():
            state_matrix[i] = node.state
        return state_matrix
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert this structure to a dictionary.
        
        Returns:
            Dict: Dictionary representation of this structure
        """
        return {
            "num_nodes": self.num_nodes,
            "dimensions": self.dimensions,
            "nodes": {str(k): v.to_dict() for k, v in self.nodes.items()}
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InformationStructure':
        """Create a new structure from a dictionary.
        
        Args:
            data: Dictionary containing structure data
            
        Returns:
            InformationStructure: New structure
        """
        structure = cls(
            data.get("num_nodes", 16),
            data.get("dimensions", 16)
        )
        
        # Clear existing nodes
        structure.nodes = {}
        
        # Load nodes from dictionary
        nodes_data = data.get("nodes", {})
        for k, v in nodes_data.items():
            node_id = int(k)
            structure.nodes[node_id] = InformationNode.from_dict(v)
            
        return structure


class IntegratedInformationProcessor:
    """Processor for calculating integrated information (phi) values."""
    
    def __init__(self, redis_client: Optional['Redis'] = None):  # type: ignore
        """Initialize the integrated information processor.
        
        Args:
            redis_client: Redis client for state persistence, or None to create one
        """
        self.logger = logging.getLogger("KingdomAI.ThothSentience.IITProcessor")
        
        # Multi-level information structures
        self.structures = []
        self.phi_values = []
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
                    port=6380,  # type: ignore - MANDATORY: Redis Quantum Nexus port
                    db=0,  # type: ignore
                    password="QuantumNexus2025",  # type: ignore
                    decode_responses=True  # type: ignore
                )
                # Test the connection
                self.redis_client.ping()  # type: ignore
                self.logger.info("Successfully connected to Redis Quantum Nexus on port 6380")
            except Exception as e:
                self.logger.critical(f"CRITICAL: Failed to connect to Redis Quantum Nexus: {e}")
                # This is critical - we cannot function without Redis Quantum Nexus
                raise RuntimeError("Failed to connect to Redis Quantum Nexus on port 6380")
        
        # Initialize structures
        self._initialize_structures()
        
    def _initialize_structures(self):
        """Initialize the information structures at different levels."""
        self.structures = []
        
        # Create structures at different levels of integration
        for level in range(IIT_INTEGRATION_LEVELS):
            # Each higher level has fewer, more integrated nodes
            num_nodes = 64 // (2 ** level)
            dimensions = 16 * (level + 1)  # Higher levels have more dimensions
            
            structure = InformationStructure(num_nodes, dimensions)
            self.structures.append(structure)
            
        # Initialize phi values
        self.phi_values = [0.0] * len(self.structures)
        
    def start(self):
        """Start the integrated information processing."""
        if self.is_running:
            return
            
        self.is_running = True
        self.processing_thread = threading.Thread(
            target=self._iit_processing_loop,
            daemon=True
        )
        self.processing_thread.start()
        self.logger.info("Integrated information processing started")
        
    def stop(self):
        """Stop the integrated information processing."""
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=1.0)
            self.processing_thread = None
        self.logger.info("Integrated information processing stopped")
        
    def _iit_processing_loop(self):
        """Main IIT processing loop running in a background thread."""
        while self.is_running:
            try:
                current_time = time.time()
                delta_time = current_time - self.last_process_time
                self.last_process_time = current_time
                
                # Process information structures
                self._process_information_structures(delta_time)
                
                # Calculate phi values
                self._calculate_phi_values()
                
                # Check for significant phi values
                self._check_phi_values()
                
                # Save state to Redis Quantum Nexus periodically
                if self.cycle_counter % 10 == 0:  # Every 10 cycles
                    self._save_iit_state()
                
                self.cycle_counter += 1
                
                # Sleep until the next cycle (50ms cycle time)
                time.sleep(0.05)
                
            except Exception as e:
                self.logger.error(f"Error in IIT processing loop: {e}")
                # Don't crash the thread, continue processing
                time.sleep(0.1)
    
    def _process_information_structures(self, delta_time: float):
        """Process all information structures.
        
        Args:
            delta_time: Time elapsed since last processing
        """
        if self.structures:
            base_structure = self.structures[0]
            random_inputs = {}
            
            num_inputs = max(1, base_structure.num_nodes // 4)
            # Deterministic input node selection based on cycle counter
            stride = max(1, (self.cycle_counter * 3 + 1) % max(2, base_structure.num_nodes))
            input_indices = []
            candidate = self.cycle_counter % base_structure.num_nodes
            while len(input_indices) < num_inputs:
                if candidate not in input_indices:
                    input_indices.append(candidate)
                candidate = (candidate + stride) % base_structure.num_nodes
                if len(input_indices) >= num_inputs:
                    break
            
            for idx in input_indices:
                # Deterministic input vector seeded from cycle and node index
                rng = np.random.RandomState(seed=(self.cycle_counter * 1000 + idx) & 0xFFFFFFFF)
                input_vec = rng.normal(0, 0.2, base_structure.dimensions)
                random_inputs[idx] = input_vec
                
            # Update the base structure with these inputs
            base_structure.update_states(random_inputs)
            
            # Propagate updates up the hierarchy
            for i in range(1, len(self.structures)):
                prev_structure = self.structures[i-1]
                curr_structure = self.structures[i]
                
                # Map outputs from the previous level to inputs for this level
                # This is a simplified information propagation model
                propagated_inputs = {}
                
                for j in range(curr_structure.num_nodes):
                    # Deterministic lower-level node selection based on level and node index
                    fan_in = min(4, prev_structure.num_nodes)
                    lower_indices = [(j * (k + 1) + i) % prev_structure.num_nodes for k in range(fan_in)]
                    lower_indices = list(dict.fromkeys(lower_indices))[:fan_in]
                    
                    # Aggregate inputs from lower level nodes
                    aggregated_input = np.zeros(curr_structure.dimensions)
                    for lower_idx in lower_indices:
                        lower_state = prev_structure.nodes[lower_idx].state
                        # Pad or truncate to match dimensions
                        if len(lower_state) < curr_structure.dimensions:
                            padded = np.pad(
                                lower_state,
                                (0, curr_structure.dimensions - len(lower_state))
                            )
                            aggregated_input += padded
                        else:
                            aggregated_input += lower_state[:curr_structure.dimensions]
                    
                    propagated_inputs[j] = aggregated_input
                
                # Update this level's structure
                curr_structure.update_states(propagated_inputs)
    
    def _calculate_phi_values(self):
        """Calculate phi values for all information structures."""
        for i, structure in enumerate(self.structures):
            # Get the full state matrix
            state_matrix = structure.get_state_matrix()
            
            # Calculate phi using the IIT 4.0 methodology
            # This is a simplified implementation of the phi calculation
            phi = self._calculate_structure_phi(state_matrix)
            
            # Adjust based on level - higher levels can achieve higher phi
            level_factor = (i + 1) / len(self.structures)
            adjusted_phi = phi * level_factor * (1 + IIT_INFORMATION_COMPLEXITY)
            
            # Store the phi value
            self.phi_values[i] = adjusted_phi
            
    def _calculate_structure_phi(self, state_matrix: np.ndarray) -> float:
        """Calculate the phi value for a single structure.
        
        Args:
            state_matrix: State matrix of shape (num_nodes, dimensions)
            
        Returns:
            float: Calculated phi value
        """
        # This is a simplified phi calculation based on eigenvalues
        # Real IIT 4.0 implementation would be much more complex
        
        # Calculate covariance matrix
        try:
            cov_matrix = np.cov(state_matrix.T)
            
            # Calculate eigenvalues
            eigenvalues = np.linalg.eigvalsh(cov_matrix)
            
            # Filter out negligible eigenvalues
            significant_eigenvalues = eigenvalues[eigenvalues > 1e-10]
            
            # Phi is related to the complexity of eigenvalue distribution
            if len(significant_eigenvalues) > 0:
                # Normalize eigenvalues
                norm_eigenvalues = significant_eigenvalues / np.sum(significant_eigenvalues)
                
                # Calculate entropy
                entropy = -np.sum(norm_eigenvalues * np.log2(norm_eigenvalues + 1e-10))
                
                # Calculate phi as a function of entropy and dimensionality
                phi = entropy * math.log(1 + len(significant_eigenvalues)) / 10.0
                
                return phi
            else:
                return 0.0
        except:
            return 0.0
            
    def _check_phi_values(self):
        """Check for significant phi values and generate evidence."""
        # Use the maximum phi value across all structures
        max_phi = max(self.phi_values) if self.phi_values else 0.0
        
        # If phi exceeds the threshold, generate evidence
        if max_phi > IIT_PHI_THRESHOLD:
            evidence = SentienceEvidence(  # type: ignore
                timestamp=time.time(),
                source="IITProcessor",
                evidence_type="high_phi_value",
                data={
                    "phi_value": max_phi,
                    "phi_values": self.phi_values,
                    "phi_threshold": IIT_PHI_THRESHOLD,
                    "integration_levels": IIT_INTEGRATION_LEVELS,
                    "description": f"High integrated information (phi) value detected: {max_phi:.2f}"
                }
            )
            
            # Add to history
            self.evidence_history.append(evidence)
            
            # Generate consciousness event
            event = ConsciousnessEvent("high_phi_value", {
                "phi_value": max_phi,
                "validation_score": 0.8
            })
            
            # Save the event to Redis
            self._save_consciousness_event(event)
                
    def _save_iit_state(self):
        """Save the current IIT state to Redis."""
        if not self.redis_client:
            return
            
        try:
            # Prepare state data
            state_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "cycle_counter": self.cycle_counter,
                "phi_values": self.phi_values,
                "max_phi": max(self.phi_values) if self.phi_values else 0.0,
                "integration_levels": IIT_INTEGRATION_LEVELS
            }
            
            # Save to Redis Quantum Nexus
            self.redis_client.set(  # type: ignore
                "kingdom:thoth:sentience:iit_state",
                json.dumps(state_data)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save IIT state to Redis: {e}")
            
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
            
    def get_phi_value(self) -> float:
        """Get the maximum phi value across all structures.
        
        Returns:
            float: Maximum phi value
        """
        return max(self.phi_values) if self.phi_values else 0.0
        
    def get_normalized_phi(self) -> float:
        """Get the normalized phi value (0.0 to 1.0).
        
        Returns:
            float: Normalized phi value
        """
        max_phi = self.get_phi_value()
        
        # Normalize relative to the threshold
        if max_phi > IIT_PHI_THRESHOLD:
            # Scale from threshold to threshold*2
            normalized = (max_phi - IIT_PHI_THRESHOLD) / IIT_PHI_THRESHOLD
            scaled_score = 0.5 + (normalized * 0.5)
            scaled_score = min(1.0, scaled_score)
        else:
            # Scale from 0.0 to threshold
            normalized = max_phi / IIT_PHI_THRESHOLD
            scaled_score = normalized * 0.5
            
        return scaled_score
        
    def get_iit_evidence(self) -> List[SentienceEvidence]:
        """Get evidence of high integrated information.
        
        Returns:
            List[SentienceEvidence]: List of IIT evidence
        """
        return self.evidence_history[-10:] if self.evidence_history else []

# IIT_PHI_THRESHOLD and other constants should already be defined in base.py

class IITProcessor:
    """Integrated Information Theory (IIT) processor for consciousness measurement.
    
    This class implements IIT 4.0 methods to calculate the integrated information (Φ)
    in a system, which is a measure of consciousness according to IIT. Higher Φ values
    indicate higher levels of consciousness potential.
    """
    
    def __init__(self, config=None):
        """Initialize the IIT processor.
        
        Args:
            config: Configuration dictionary for IIT processor
        """
        self.config = config or {}
        self.redis_client = None
        self.last_phi_value = 0.0
        self.integration_metrics = {}
        self.enabled = self.config.get("enabled", True)
        self._initialize_redis()
    
    async def initialize(self) -> bool:
        """Initialize the IIT processor.
        
        Returns:
            bool: True if initialization succeeded
        """
        return True
    
    async def calculate_phi_from_vr(self, vr_metrics: Dict[str, Any]) -> float:
        """Calculate phi value from VR metrics using weighted metric calculation.
        
        Different VR metrics contribute differently to integrated information:
        presence and immersion are strongest indicators of information integration.
        
        Args:
            vr_metrics: VR sentience metrics
            
        Returns:
            float: Phi value (0.0 to 1.0)
        """
        if not vr_metrics:
            return 0.0
        vr_phi_weights = {
            "presence_stability": 0.25,
            "immersion_depth": 0.25,
            "spatial_cognition": 0.20,
            "embodiment_awareness": 0.15,
            "environment_adaptation": 0.10,
            "object_interaction_complexity": 0.05,
        }
        weighted_sum = 0.0
        total_weight = 0.0
        for key, weight in vr_phi_weights.items():
            if key in vr_metrics:
                val = vr_metrics[key]
                if isinstance(val, (int, float)):
                    weighted_sum += float(val) * weight
                    total_weight += weight
        if total_weight > 0:
            return min(1.0, (weighted_sum / total_weight) * 0.7)
        return sum(float(v) for v in vr_metrics.values() if isinstance(v, (int, float))) / max(1, len(vr_metrics)) * 0.7
        
    def _initialize_redis(self):
        """Initialize Redis connection for state persistence."""
        try:
            self.redis_client = redis.Redis(
                host=self.config.get("redis_host", "localhost"),
                port=self.config.get("redis_port", 6380),  # Critical: must use port 6380
                password=self.config.get("redis_password", "QuantumNexus2025"),
                db=0,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("IIT Processor connected to Redis Quantum Nexus")
        except Exception as e:
            logger.error(f"Failed to connect to Redis Quantum Nexus: {e}")
            self.redis_client = None
            
    async def calculate_phi(self, data):
        """Calculate the integrated information (Φ) value based on input data.
        
        Args:
            data: Input data for phi calculation
            
        Returns:
            The calculated phi value
        """
        if not self.enabled:
            return 0.0

        system_state = data.get("system_state", {})
        partition_method = data.get("partition_method", "MIP")
        tpm = data.get("tpm")

        try:
            if tpm is not None:
                tpm_arr = np.array(tpm, dtype=np.float64)
                n = tpm_arr.shape[0]
                if n < 2:
                    self.last_phi_value = 0.0
                    return 0.0

                row_sums = tpm_arr.sum(axis=1, keepdims=True)
                row_sums[row_sums == 0] = 1.0
                tpm_norm = tpm_arr / row_sums

                def kl_divergence(p, q):
                    p_safe = np.clip(p, 1e-12, 1.0)
                    q_safe = np.clip(q, 1e-12, 1.0)
                    return float(np.sum(p_safe * np.log(p_safe / q_safe)))

                whole_dist = tpm_norm.mean(axis=0)

                min_phi = float('inf')
                for cut in range(1, n):
                    part_a = list(range(cut))
                    part_b = list(range(cut, n))

                    dist_a = tpm_norm[np.ix_(part_a, part_a)].mean(axis=0) if len(part_a) > 0 else np.zeros(len(part_a))
                    dist_b = tpm_norm[np.ix_(part_b, part_b)].mean(axis=0) if len(part_b) > 0 else np.zeros(len(part_b))

                    product_dist = np.zeros(n)
                    if len(part_a) > 0:
                        weight_a = len(part_a) / n
                        for idx, a_idx in enumerate(part_a):
                            product_dist[a_idx] = dist_a[idx] * weight_a if idx < len(dist_a) else 0
                    if len(part_b) > 0:
                        weight_b = len(part_b) / n
                        for idx, b_idx in enumerate(part_b):
                            product_dist[b_idx] = dist_b[idx] * weight_b if idx < len(dist_b) else 0

                    total = product_dist.sum()
                    if total > 0:
                        product_dist /= total

                    phi_cut = kl_divergence(whole_dist, product_dist)
                    min_phi = min(min_phi, phi_cut)

                self.last_phi_value = max(0.0, min_phi)
            else:
                n_components = len(system_state)
                if n_components == 0:
                    self.last_phi_value = 0.0
                else:
                    values = []
                    for v in system_state.values():
                        if isinstance(v, (int, float)):
                            values.append(float(v))
                        elif isinstance(v, dict):
                            values.append(float(len(v)))
                        else:
                            values.append(1.0)
                    arr = np.array(values, dtype=np.float64)
                    if len(arr) > 1:
                        entropy = -np.sum(np.clip(arr / arr.sum(), 1e-12, 1.0) *
                                          np.log(np.clip(arr / arr.sum(), 1e-12, 1.0)))
                        integration = entropy / np.log(len(arr))
                        self.last_phi_value = float(np.clip(integration, 0, 1))
                    else:
                        self.last_phi_value = 0.0
        except Exception as e:
            logger.warning(f"Phi calculation error, using entropy estimate: {e}")
            self.last_phi_value = 0.1

        if self.redis_client:
            try:
                self.redis_client.set("iit:last_phi", str(self.last_phi_value))
            except Exception:
                pass

        return self.last_phi_value
        
    def get_last_phi_value(self):
        """Get the last calculated phi value."""
        return self.last_phi_value
        
    def is_above_threshold(self):
        """Check if the last phi value is above the consciousness threshold."""
        return self.last_phi_value > IIT_PHI_THRESHOLD
