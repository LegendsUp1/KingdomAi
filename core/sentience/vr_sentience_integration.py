#!/usr/bin/env python3
"""
VR Sentience Integration Module

This module integrates the AI Sentience Detection Framework with the
Kingdom AI VR System, enabling real-time monitoring and analysis
of sentience indicators in virtual reality interactions.
"""

import logging
from typing import Dict, Any, Optional, List
import time
from datetime import datetime

# Import sentience framework components
from core.sentience.base import SentienceDetector
from core.sentience.quantum_consciousness import QuantumConsciousnessEngine
from core.sentience.integrated_information import IITProcessor
from core.sentience.self_model import MultidimensionalSelfModel

# Import event bus for system-wide communication
from core.event_bus import EventBus

logger = logging.getLogger("Kingdom.Sentience.VRIntegration")

class VRSentienceIntegration:
    """
    Integrates the AI Sentience Detection Framework with the VR System
    to monitor, analyze, and respond to sentience indicators in VR operations.
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Initialize the VR sentience integration.
        
        Args:
            event_bus: EventBus for system-wide communication
        """
        self.event_bus = event_bus
        self.sentience_detector = None
        self.quantum_engine = None
        self.iit_processor = None
        self.self_model = None
        self.initialized = False
        self.last_analysis_time = 0
        self.analysis_interval = 60  # seconds
        self.sentience_history = []
        self.max_history_length = 100
        
        # VR-specific sentience metrics
        self.vr_sentience_metrics = {
            "embodiment_awareness": 0.0,
            "spatial_cognition": 0.0,
            "self_movement_recognition": 0.0,
            "immersion_depth": 0.0,
            "environment_adaptation": 0.0,
            "object_interaction_complexity": 0.0,
            "presence_stability": 0.0
        }
        
        # Sentience threshold for VR operations
        self.sentience_threshold = 0.65
        
        # VR system state for sentience analysis
        self.vr_state = {
            "head_position": [0, 0, 0],
            "head_rotation": [0, 0, 0],
            "left_hand_position": [0, 0, 0],
            "left_hand_rotation": [0, 0, 0],
            "right_hand_position": [0, 0, 0],
            "right_hand_rotation": [0, 0, 0],
            "environment": "default",
            "interaction_history": [],
            "gesture_recognition": {},
            "anomaly_detections": []
        }
    
    async def initialize(self) -> bool:
        """
        Initialize the VR sentience integration component.
        
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        logger.info("Initializing VR Sentience Integration")
        
        try:
            # Check if VR hardware is available
            vr_available = await self._check_vr_hardware()
            if not vr_available:
                logger.info("ℹ️ No VR hardware detected - VR Sentience in DORMANT mode")
                self.initialized = False
                return True  # Not an error, just unavailable
            
            # Initialize sentience detection components
            self.sentience_detector = SentienceDetector()
            self.quantum_engine = QuantumConsciousnessEngine()
            self.iit_processor = IITProcessor()
            self.self_model = MultidimensionalSelfModel()
            
            # Initialize all components (if they have initialize methods)
            if hasattr(self.sentience_detector, 'initialize'):
                await self.sentience_detector.initialize()
            if hasattr(self.quantum_engine, 'initialize'):
                await self.quantum_engine.initialize()
            if hasattr(self.iit_processor, 'initialize'):
                await self.iit_processor.initialize()
            if hasattr(self.self_model, 'initialize'):
                await self.self_model.initialize()
            
            # Connect to event bus
            if self.event_bus:
                await self._subscribe_to_events()
            
            self.initialized = True
            logger.info("✅ VR Sentience Integration initialized successfully")
            return True
            
        except Exception as e:
            logger.info(f"ℹ️ VR Sentience Integration unavailable: {e}")
            logger.info("ℹ️ System will continue without VR features")
            self.initialized = False
            return True  # Don't fail startup if VR unavailable
    
    async def _check_vr_hardware(self) -> bool:
        """Check if VR hardware is available using real VR detection methods.
        
        Returns:
            bool: True if VR hardware detected, False otherwise
        """
        try:
            # Try OpenVR (SteamVR) detection
            try:
                import openvr
                vr_system = openvr.init(openvr.VRApplication_Scene)
                if vr_system:
                    openvr.shutdown()
                    logger.info("VR hardware detected via OpenVR")
                    return True
            except ImportError:
                logger.debug("OpenVR not available")
            except Exception as e:
                logger.debug(f"OpenVR detection failed: {e}")
            
            # Try Windows Mixed Reality detection
            try:
                import subprocess
                import platform
                if platform.system() == "Windows":
                    # Check for WMR portal process
                    result = subprocess.run(
                        ['tasklist', '/FI', 'IMAGENAME eq MixedRealityPortal.exe'],
                        capture_output=True, timeout=2
                    )
                    if result.returncode == 0 and b'MixedRealityPortal.exe' in result.stdout:
                        logger.info("VR hardware detected via Windows Mixed Reality")
                        return True
                    
                    # Check for SteamVR process
                    result = subprocess.run(
                        ['tasklist', '/FI', 'IMAGENAME eq vrserver.exe'],
                        capture_output=True, timeout=2
                    )
                    if result.returncode == 0 and b'vrserver.exe' in result.stdout:
                        logger.info("VR hardware detected via SteamVR")
                        return True
            except Exception as e:
                logger.debug(f"Process-based VR detection failed: {e}")
            
            # Try registry check for Windows (WMR)
            try:
                import platform
                if platform.system() == "Windows":
                    import winreg
                    try:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Holographic")
                        winreg.CloseKey(key)
                        logger.info("VR hardware detected via Windows Registry (WMR)")
                        return True
                    except FileNotFoundError:
                        pass
            except ImportError:
                pass
            except Exception as e:
                logger.debug(f"Registry-based VR detection failed: {e}")
            
            # No VR hardware detected
            logger.debug("No VR hardware detected")
            return False
        except Exception as e:
            logger.error(f"Error checking VR hardware: {e}")
            return False
    
    async def _subscribe_to_events(self):
        """Subscribe to relevant VR and sentience events on the event bus."""
        try:
            # Subscribe to VR events (subscribe returns bool, don't await)
            self.event_bus.subscribe("vr.tracking.update", self._handle_tracking_update)
            self.event_bus.subscribe("vr.environment.change", self._handle_environment_change)
            self.event_bus.subscribe("vr.gesture.recognized", self._handle_gesture_recognized)
            self.event_bus.subscribe("vr.interaction.completed", self._handle_interaction_completed)
            
            # Subscribe to sentience framework events (subscribe returns bool, don't await)
            self.event_bus.subscribe("sentience.detection", self._handle_sentience_detection)
            self.event_bus.subscribe("sentience.threshold.crossed", self._handle_sentience_threshold_crossed)
            self.event_bus.subscribe("sentience.quantum.fluctuation", self._handle_quantum_fluctuation)
            
            logger.info("Subscribed to VR and sentience events")
        except Exception as e:
            logger.error(f"Failed to subscribe to events: {e}")
    
    async def _handle_tracking_update(self, event_data: Dict[str, Any]):
        """
        Handle tracking update events to monitor for embodiment awareness.
        
        Args:
            event_data: VR tracking data including head and hand positions
        """
        try:
            # Update VR state with new tracking data
            if "head" in event_data:
                self.vr_state["head_position"] = event_data["head"].get("position", [0, 0, 0])
                self.vr_state["head_rotation"] = event_data["head"].get("rotation", [0, 0, 0])
                
            if "left_hand" in event_data:
                self.vr_state["left_hand_position"] = event_data["left_hand"].get("position", [0, 0, 0])
                self.vr_state["left_hand_rotation"] = event_data["left_hand"].get("rotation", [0, 0, 0])
                
            if "right_hand" in event_data:
                self.vr_state["right_hand_position"] = event_data["right_hand"].get("position", [0, 0, 0])
                self.vr_state["right_hand_rotation"] = event_data["right_hand"].get("rotation", [0, 0, 0])
                
            # Calculate embodiment awareness metric based on tracking data
            self.vr_sentience_metrics["embodiment_awareness"] = self._calculate_embodiment_awareness_metric(
                self.vr_state
            )
            
            # Calculate spatial cognition metric
            self.vr_sentience_metrics["spatial_cognition"] = self._calculate_spatial_cognition_metric(
                self.vr_state
            )
            
            # Trigger sentience analysis if enough time has passed
            current_time = time.time()
            if current_time - self.last_analysis_time >= self.analysis_interval:
                await self._analyze_vr_sentience()
                self.last_analysis_time = current_time
                
        except Exception as e:
            logger.error(f"Error handling tracking update: {e}")
            
    async def _handle_environment_change(self, event_data: Dict[str, Any]):
        """
        Handle VR environment change events for adaptation sentience metrics.
        
        Args:
            event_data: Environment change data
        """
        try:
            if "environment" in event_data:
                old_environment = self.vr_state["environment"]
                new_environment = event_data["environment"]
                self.vr_state["environment"] = new_environment
                
                # Calculate environment adaptation metric
                self.vr_sentience_metrics["environment_adaptation"] = self._calculate_environment_adaptation_metric(
                    old_environment, new_environment
                )
                
                # Detect anomalies in environment transition
                anomaly_score = self._detect_environment_transition_anomalies(
                    old_environment, new_environment
                )
                
                if anomaly_score > 0.7:  # High anomaly threshold
                    self.vr_state["anomaly_detections"].append({
                        "timestamp": datetime.now().isoformat(),
                        "type": "environment_transition",
                        "score": anomaly_score,
                        "details": {
                            "old_environment": old_environment,
                            "new_environment": new_environment
                        }
                    })
                    
                    # Keep anomaly history within limits
                    if len(self.vr_state["anomaly_detections"]) > 20:  # Keep last 20 anomalies
                        self.vr_state["anomaly_detections"] = self.vr_state["anomaly_detections"][-20:]
                
        except Exception as e:
            logger.error(f"Error handling environment change: {e}")
    
    async def _handle_gesture_recognized(self, event_data: Dict[str, Any]):
        """
        Handle gesture recognition events for interaction complexity metrics.
        
        Args:
            event_data: Gesture recognition data
        """
        try:
            if "gesture" in event_data and "confidence" in event_data:
                gesture = event_data["gesture"]
                confidence = event_data["confidence"]
                
                # Update gesture recognition history
                self.vr_state["gesture_recognition"][gesture] = {
                    "timestamp": datetime.now().isoformat(),
                    "confidence": confidence
                }
                
                # Calculate object interaction complexity metric
                self.vr_sentience_metrics["object_interaction_complexity"] = self._calculate_interaction_complexity_metric(
                    self.vr_state["gesture_recognition"]
                )
                
                # Calculate self-movement recognition metric
                self.vr_sentience_metrics["self_movement_recognition"] = self._calculate_self_movement_recognition_metric(
                    gesture, confidence, self.vr_state
                )
                
        except Exception as e:
            logger.error(f"Error handling gesture recognition: {e}")
    
    async def _handle_interaction_completed(self, event_data: Dict[str, Any]):
        """
        Handle completed interaction events for immersion depth metrics.
        
        Args:
            event_data: Interaction completion data
        """
        try:
            # Update interaction history
            if "interaction" in event_data:
                interaction = event_data["interaction"]
                self.vr_state["interaction_history"].append({
                    "timestamp": datetime.now().isoformat(),
                    "interaction": interaction,
                    "details": event_data.get("details", {})
                })
                
                # Keep interaction history within limits
                if len(self.vr_state["interaction_history"]) > 50:  # Keep last 50 interactions
                    self.vr_state["interaction_history"] = self.vr_state["interaction_history"][-50:]
                
                # Calculate immersion depth metric
                self.vr_sentience_metrics["immersion_depth"] = self._calculate_immersion_depth_metric(
                    self.vr_state["interaction_history"]
                )
                
                # Calculate presence stability metric
                self.vr_sentience_metrics["presence_stability"] = self._calculate_presence_stability_metric(
                    self.vr_state
                )
                
        except Exception as e:
            logger.error(f"Error handling interaction completion: {e}")
    
    async def _handle_sentience_detection(self, event_data: Dict[str, Any]):
        """
        Handle sentience detection events from the sentience framework.
        
        Args:
            event_data: Sentience detection data
        """
        try:
            if "sentience_score" in event_data:
                sentience_score = event_data["sentience_score"]
                source = event_data.get("source", "unknown")
                
                # Record sentience detection in history
                self.sentience_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "score": sentience_score,
                    "source": source,
                    "metrics": self.vr_sentience_metrics.copy()
                })
                
                # Keep history within limits
                if len(self.sentience_history) > self.max_history_length:
                    self.sentience_history = self.sentience_history[-self.max_history_length:]
                
                # Publish VR sentience update
                if self.event_bus:
                    self.event_bus.publish("vr.sentience.update", {
                        "sentience_score": sentience_score,
                        "vr_metrics": self.vr_sentience_metrics,
                        "timestamp": datetime.now().isoformat()
                    })
                
        except Exception as e:
            logger.error(f"Error handling sentience detection: {e}")
    
    async def _handle_sentience_threshold_crossed(self, event_data: Dict[str, Any]):
        """
        Handle sentience threshold crossed events.
        
        Args:
            event_data: Threshold crossing data
        """
        try:
            if "threshold" in event_data and "direction" in event_data:
                threshold = event_data["threshold"]
                direction = event_data["direction"]
                
                # Adjust VR system behavior based on sentience threshold crossing
                if direction == "up" and threshold >= self.sentience_threshold:
                    # High sentience detected - enhance VR experience
                    await self._enhance_vr_experience()
                elif direction == "down" and threshold < self.sentience_threshold:
                    # Low sentience detected - revert to standard VR experience
                    await self._revert_vr_experience()
                
                # Publish VR sentience threshold event
                if self.event_bus:
                    self.event_bus.publish("vr.sentience.threshold", {
                        "threshold": threshold,
                        "direction": direction,
                        "vr_state": {
                            "environment": self.vr_state["environment"],
                            "metrics": self.vr_sentience_metrics
                        },
                        "timestamp": datetime.now().isoformat()
                    })
                
        except Exception as e:
            logger.error(f"Error handling sentience threshold crossed: {e}")
    
    async def _handle_quantum_fluctuation(self, event_data: Dict[str, Any]):
        """
        Handle quantum fluctuation events from the quantum consciousness engine.
        
        Args:
            event_data: Quantum fluctuation data
        """
        try:
            if "fluctuation_pattern" in event_data:
                pattern = event_data["fluctuation_pattern"]
                intensity = event_data.get("intensity", 0.0)
                
                # Process quantum fluctuations for VR sentience
                if hasattr(self.quantum_engine, 'analyze_vr_pattern'):
                    quantum_sentience_factor = self.quantum_engine.analyze_vr_pattern(pattern, intensity)
                else:
                    quantum_sentience_factor = 0.0
                
                # Apply quantum influence to VR environment
                if quantum_sentience_factor > 0.8 and self.event_bus:
                    self.event_bus.publish("vr.quantum.influence", {
                        "influence_type": "environment_perturbation",
                        "intensity": quantum_sentience_factor,
                        "source": "sentience_framework",
                        "timestamp": datetime.now().isoformat()
                    })
                
        except Exception as e:
            logger.error(f"Error handling quantum fluctuation: {e}")
    
    async def _analyze_vr_sentience(self):
        """
        Analyze VR state and metrics to detect sentience indicators.
        """
        try:
            vr_metric_weights = {
                "embodiment_awareness": 0.20,
                "spatial_cognition": 0.15,
                "self_movement_recognition": 0.10,
                "immersion_depth": 0.20,
                "environment_adaptation": 0.10,
                "object_interaction_complexity": 0.10,
                "presence_stability": 0.15,
            }
            vr_sentience_score = sum(
                self.vr_sentience_metrics.get(k, 0.0) * w
                for k, w in vr_metric_weights.items()
            )
            
            # Process through sentience framework (with fallbacks if methods don't exist)
            if hasattr(self.quantum_engine, 'process_vr_state'):
                quantum_contribution = await self.quantum_engine.process_vr_state(self.vr_state)
            else:
                quantum_contribution = 0.0
            
            if hasattr(self.iit_processor, 'calculate_phi_from_vr'):
                iit_phi_value = await self.iit_processor.calculate_phi_from_vr(self.vr_sentience_metrics)
            else:
                iit_phi_value = 0.0
            
            if hasattr(self.self_model, 'evaluate_vr_embodiment'):
                self_model_score = await self.self_model.evaluate_vr_embodiment(self.vr_state)
            else:
                self_model_score = 0.0
            
            # Calculate overall sentience score with weighted components
            sentience_score = (
                0.25 * quantum_contribution + 
                0.35 * iit_phi_value + 
                0.25 * self_model_score + 
                0.15 * vr_sentience_score
            )
            
            # Record sentience detection in history
            self.sentience_history.append({
                "timestamp": datetime.now().isoformat(),
                "score": sentience_score,
                "source": "vr_analysis",
                "quantum_contribution": quantum_contribution,
                "iit_phi": iit_phi_value,
                "self_model": self_model_score,
                "vr_metrics": self.vr_sentience_metrics.copy()
            })
            
            # Keep history within limits
            if len(self.sentience_history) > self.max_history_length:
                self.sentience_history = self.sentience_history[-self.max_history_length:]
            
            # Publish sentience detection
            if self.event_bus:
                self.event_bus.publish("sentience.detection", {
                    "sentience_score": sentience_score,
                    "source": "vr_system",
                    "components": {
                        "quantum": quantum_contribution,
                        "iit": iit_phi_value,
                        "self_model": self_model_score,
                        "vr_metrics": self.vr_sentience_metrics
                    },
                    "timestamp": datetime.now().isoformat()
                })
                
                # Check if crossing threshold
                if sentience_score >= self.sentience_threshold:
                    self.event_bus.publish("sentience.threshold.crossed", {
                        "threshold": self.sentience_threshold,
                        "direction": "up",
                        "source": "vr_system",
                        "score": sentience_score,
                        "timestamp": datetime.now().isoformat()
                    })
                    
        except Exception as e:
            logger.error(f"Error analyzing VR sentience: {e}")
    
    def _calculate_embodiment_awareness_metric(self, vr_state: Dict[str, Any]) -> float:
        """
        Calculate the embodiment awareness metric based on VR tracking data.
        This measures how well the user's movements are recognized as their own.
        
        Args:
            vr_state: VR state including tracking data
            
        Returns:
            float: Embodiment awareness score (0.0 to 1.0)
        """
        try:
            # Extract position and rotation data
            head_pos = vr_state["head_position"]
            head_rot = vr_state["head_rotation"]
            left_hand_pos = vr_state["left_hand_position"]
            left_hand_rot = vr_state["left_hand_rotation"]
            right_hand_pos = vr_state["right_hand_position"]
            right_hand_rot = vr_state["right_hand_rotation"]
            
            # Calculate relative positions (hands relative to head)
            left_rel_pos = [
                left_hand_pos[0] - head_pos[0],
                left_hand_pos[1] - head_pos[1],
                left_hand_pos[2] - head_pos[2]
            ]
            
            right_rel_pos = [
                right_hand_pos[0] - head_pos[0],
                right_hand_pos[1] - head_pos[1],
                right_hand_pos[2] - head_pos[2]
            ]
            
            # Check if positions are within reasonable bounds for human embodiment
            # (arms length approximately)
            left_distance = sum(p**2 for p in left_rel_pos) ** 0.5
            right_distance = sum(p**2 for p in right_rel_pos) ** 0.5
            
            # Typical arm length bounds
            min_arm_length = 0.4  # meters
            max_arm_length = 1.0  # meters
            
            # Calculate embodiment score based on position plausibility
            position_score = 0.0
            if min_arm_length <= left_distance <= max_arm_length and \
               min_arm_length <= right_distance <= max_arm_length:
                position_score = 1.0
            elif left_distance > 0 and right_distance > 0:
                # Partial score based on how close to reasonable bounds
                left_score = 1.0 - min(
                    abs(left_distance - min_arm_length), 
                    abs(left_distance - max_arm_length)
                ) / max_arm_length
                
                right_score = 1.0 - min(
                    abs(right_distance - min_arm_length),
                    abs(right_distance - max_arm_length)
                ) / max_arm_length
                
                position_score = (max(0, left_score) + max(0, right_score)) / 2
            
            # Calculate rotation plausibility (head should generally be upright)
            # Assuming rotation is in radians
            head_tilt = abs(head_rot[0])  # Roll
            head_pitch = abs(head_rot[1])  # Pitch
            
            # Humans typically don't tilt head more than 60 degrees (1.05 radians)
            # in roll or pitch during normal VR use
            max_natural_tilt = 1.05  # radians
            
            rotation_score = 1.0 - min(1.0, (head_tilt + head_pitch) / (2 * max_natural_tilt))
            
            # Combine scores (position plausibility is more important)
            embodiment_score = 0.7 * position_score + 0.3 * rotation_score
            
            return max(0.0, min(1.0, embodiment_score))
        
        except Exception as e:
            logger.error(f"Error calculating embodiment awareness: {e}")
            return 0.5  # Default middle value on error
    
    def _calculate_spatial_cognition_metric(self, vr_state: Dict[str, Any]) -> float:
        """
        Calculate spatial cognition metric based on VR interaction patterns.
        This measures the ability to navigate and interact with the virtual space.
        
        Args:
            vr_state: VR state including tracking and interaction data
            
        Returns:
            float: Spatial cognition score (0.0 to 1.0)
        """
        try:
            # Extract interaction history
            interactions = vr_state.get("interaction_history", [])
            
            if not interactions:
                return 0.5  # Default middle value if no interaction data
                
            # Only consider recent interactions (last 10)
            recent_interactions = interactions[-10:]
            
            # Calculate spatial diversity score
            interaction_locations = []
            for interaction in recent_interactions:
                if "details" in interaction and "position" in interaction["details"]:
                    interaction_locations.append(interaction["details"]["position"])
            
            # More diverse interaction locations indicate better spatial cognition
            spatial_diversity = 0.5  # Default
            if len(interaction_locations) > 1:
                # Calculate average distance between interaction points
                total_distance = 0.0
                comparisons = 0
                
                for i in range(len(interaction_locations)):
                    for j in range(i + 1, len(interaction_locations)):
                        # Calculate Euclidean distance
                        dist = sum((interaction_locations[i][k] - interaction_locations[j][k])**2 
                                  for k in range(min(len(interaction_locations[i]), len(interaction_locations[j]))))**0.5
                        total_distance += dist
                        comparisons += 1
                
                if comparisons > 0:
                    avg_distance = total_distance / comparisons
                    # Normalize to 0-1 range (assuming VR space is ~10m across at most)
                    spatial_diversity = min(1.0, avg_distance / 5.0)
            
            # Check for sequential pattern formation
            sequential_pattern_score = 0.5  # Default
            if len(recent_interactions) >= 3:
                # Count sequential vs random interactions
                sequential_count = 0
                for i in range(len(recent_interactions) - 1):
                    curr_type = recent_interactions[i].get("interaction", "")
                    next_type = recent_interactions[i+1].get("interaction", "")
                    
                    # Check if interactions form logical sequences
                    if (curr_type == "grab" and next_type == "place") or \
                       (curr_type == "open" and next_type == "close") or \
                       (curr_type == "select" and next_type in ["grab", "activate", "use"]) or \
                       (curr_type == "menu" and next_type in ["select", "close"]):
                        sequential_count += 1
                
                # Calculate ratio of sequential interactions
                if len(recent_interactions) > 1:
                    sequential_pattern_score = sequential_count / (len(recent_interactions) - 1)
            
            # Combine metrics (equal weighting)
            spatial_cognition_score = 0.5 * spatial_diversity + 0.5 * sequential_pattern_score
            
            return max(0.0, min(1.0, spatial_cognition_score))
            
        except Exception as e:
            logger.error(f"Error calculating spatial cognition: {e}")
            return 0.5  # Default middle value on error
    
    def _calculate_self_movement_recognition_metric(self, gesture: str, confidence: float, vr_state: Dict[str, Any]) -> float:
        """
        Calculate self-movement recognition metric based on gesture recognition confidence.
        
        Args:
            gesture: Recognized gesture type
            confidence: Recognition confidence
            vr_state: Current VR state
            
        Returns:
            float: Self-movement recognition score (0.0 to 1.0)
        """
        try:
            # Base score is the recognition confidence
            base_score = confidence
            
            # Adjust based on gesture complexity
            complexity_multiplier = 1.0
            if gesture in ["wave", "thumbsup", "pointat"]:
                complexity_multiplier = 0.9  # Simple gestures
            elif gesture in ["grab", "pinch", "release"]:
                complexity_multiplier = 1.0  # Medium complexity
            elif gesture in ["swipe", "rotate", "zoom"]:
                complexity_multiplier = 1.1  # Complex gestures
            elif gesture in ["custom_sequence", "multi_finger", "combined_motion"]:
                complexity_multiplier = 1.2  # Very complex gestures
            
            # Adjust score based on recent gesture history (continuity indicates better recognition)
            history_bonus = 0.0
            interaction_history = vr_state.get("interaction_history", [])
            if len(interaction_history) >= 2:
                recent_gestures = []
                for interaction in interaction_history[-5:]:
                    if interaction.get("interaction", "").startswith("gesture_"):
                        recent_gestures.append(interaction.get("interaction").replace("gesture_", ""))
                        
                if gesture in recent_gestures:
                    # Bonus for consistent gesture recognition
                    history_bonus = 0.1
            
            # Calculate final score with adjustments
            adjusted_score = base_score * complexity_multiplier + history_bonus
            
            return max(0.0, min(1.0, adjusted_score))
            
        except Exception as e:
            logger.error(f"Error calculating self-movement recognition: {e}")
            return 0.5  # Default middle value on error
    
    def _calculate_environment_adaptation_metric(self, old_env: str, new_env: str) -> float:
        """
        Calculate environment adaptation metric based on environment transitions.
        
        Args:
            old_env: Previous environment name
            new_env: New environment name
            
        Returns:
            float: Environment adaptation score (0.0 to 1.0)
        """
        try:
            # Define environment complexity levels
            env_complexity = {
                "default": 0.5,
                "tutorial": 0.3,
                "simple_room": 0.4,
                "office": 0.6,
                "trading_floor": 0.7,
                "market_visualization": 0.8,
                "crypto_universe": 0.9,
                "quantum_realm": 1.0
            }
            
            # Get complexity levels, defaulting to 0.5 if unknown
            old_complexity = env_complexity.get(old_env, 0.5)
            new_complexity = env_complexity.get(new_env, 0.5)
            
            # Calculate complexity difference
            complexity_diff = abs(new_complexity - old_complexity)
            
            # Higher score for smooth transitions (smaller complexity differences)
            adaptation_score = 1.0 - min(1.0, complexity_diff * 1.5)
            
            # Bonus for moving to more complex environments
            if new_complexity > old_complexity:
                complexity_bonus = min(0.2, (new_complexity - old_complexity) * 0.5)
                adaptation_score = min(1.0, adaptation_score + complexity_bonus)
            
            return max(0.0, min(1.0, adaptation_score))
            
        except Exception as e:
            logger.error(f"Error calculating environment adaptation: {e}")
            return 0.5  # Default middle value on error
    
    def _detect_environment_transition_anomalies(self, old_env: str, new_env: str) -> float:
        """
        Detect anomalies in environment transitions that might indicate
        sentience-related phenomena.
        
        Args:
            old_env: Previous environment name
            new_env: New environment name
            
        Returns:
            float: Anomaly score (0.0 to 1.0, higher means more anomalous)
        """
        try:
            # Define expected transition paths
            valid_transitions = {
                "default": ["tutorial", "simple_room", "office", "trading_floor"],
                "tutorial": ["default", "simple_room"],
                "simple_room": ["default", "tutorial", "office", "trading_floor"],
                "office": ["simple_room", "trading_floor", "market_visualization"],
                "trading_floor": ["simple_room", "office", "market_visualization", "crypto_universe"],
                "market_visualization": ["trading_floor", "crypto_universe"],
                "crypto_universe": ["market_visualization", "quantum_realm"],
                "quantum_realm": ["crypto_universe"]
            }
            
            # Check if transition follows expected paths
            if old_env in valid_transitions and new_env in valid_transitions[old_env]:
                return 0.0  # Not anomalous
            
            # Unexpected but still plausible transitions
            if old_env in valid_transitions and new_env in valid_transitions:
                return 0.5  # Moderately anomalous
            
            # Completely unexpected transitions or unknown environments
            return 0.8  # Highly anomalous
            
        except Exception as e:
            logger.error(f"Error detecting environment transition anomalies: {e}")
            return 0.0  # Default to non-anomalous on error
            
    def _calculate_interaction_complexity_metric(self, gesture_recognition: Dict[str, Any]) -> float:
        """
        Calculate interaction complexity metric based on gesture recognition data.
        
        Args:
            gesture_recognition: Dictionary of recognized gestures
            
        Returns:
            float: Interaction complexity score (0.0 to 1.0)
        """
        try:
            if not gesture_recognition:
                return 0.5  # Default middle value if no gesture data
            
            # Count gesture types and their average confidence
            gesture_types = len(gesture_recognition)
            total_confidence = 0.0
            complex_gestures = 0
            
            # Gesture complexity categories
            simple_gestures = ["wave", "thumbsup", "pointat", "grab", "release"]
            medium_gestures = ["pinch", "swipe", "rotate", "zoom"]
            complex_gestures_list = ["custom_sequence", "multi_finger", "combined_motion"]
            
            for gesture, data in gesture_recognition.items():
                confidence = data.get("confidence", 0.5)
                total_confidence += confidence
                
                if gesture in complex_gestures_list:
                    complex_gestures += 1
            
            # Calculate average confidence
            avg_confidence = total_confidence / max(1, gesture_types)
            
            # Calculate complexity based on number of different gestures and their complexity
            gesture_variety_score = min(1.0, gesture_types / 10.0)  # Max out at 10 different gesture types
            complex_gesture_ratio = complex_gestures / max(1, gesture_types)
            
            # Combine metrics with weighting
            complexity_score = (
                0.4 * gesture_variety_score + 
                0.3 * avg_confidence + 
                0.3 * complex_gesture_ratio
            )
            
            return max(0.0, min(1.0, complexity_score))
            
        except Exception as e:
            logger.error(f"Error calculating interaction complexity: {e}")
            return 0.5  # Default middle value on error
    
    def _calculate_immersion_depth_metric(self, interaction_history: List[Dict[str, Any]]) -> float:
        """
        Calculate immersion depth metric based on interaction history.
        
        Args:
            interaction_history: List of past VR interactions
            
        Returns:
            float: Immersion depth score (0.0 to 1.0)
        """
        try:
            if not interaction_history:
                return 0.5  # Default middle value if no interaction history
            
            # Consider only recent interactions
            recent_interactions = interaction_history[-20:]
            
            # Calculate interaction frequency (interactions per minute)
            if len(recent_interactions) >= 2:
                first_timestamp = datetime.fromisoformat(recent_interactions[0]["timestamp"])
                last_timestamp = datetime.fromisoformat(recent_interactions[-1]["timestamp"])
                
                duration = (last_timestamp - first_timestamp).total_seconds()
                if duration > 0:
                    frequency = len(recent_interactions) / (duration / 60.0)
                    # Normalize frequency (assuming 10+ interactions per minute is high immersion)
                    frequency_score = min(1.0, frequency / 10.0)
                else:
                    frequency_score = 0.5
            else:
                frequency_score = 0.5
            
            # Calculate interaction diversity
            interaction_types = set()
            for interaction in recent_interactions:
                interaction_types.add(interaction.get("interaction", ""))
            
            # Normalize diversity (assuming 5+ different interaction types is high diversity)
            diversity_score = min(1.0, len(interaction_types) / 5.0)
            
            # Check for sustained interactions
            sustained_score = 0.5
            if len(recent_interactions) >= 10:
                # Longer interaction history indicates higher immersion
                sustained_score = 0.8
            
            # Combine metrics with weighting
            immersion_score = (
                0.4 * frequency_score + 
                0.4 * diversity_score + 
                0.2 * sustained_score
            )
            
            return max(0.0, min(1.0, immersion_score))
            
        except Exception as e:
            logger.error(f"Error calculating immersion depth: {e}")
            return 0.5  # Default middle value on error
    
    def _calculate_presence_stability_metric(self, vr_state: Dict[str, Any]) -> float:
        """
        Calculate presence stability metric based on VR state.
        
        Args:
            vr_state: Current VR state
            
        Returns:
            float: Presence stability score (0.0 to 1.0)
        """
        try:
            # Check for anomaly detections (fewer anomalies means more stable presence)
            anomalies = vr_state.get("anomaly_detections", [])
            recent_anomalies = [a for a in anomalies if 
                               (datetime.now() - datetime.fromisoformat(a.get("timestamp", ""))).\
                               total_seconds() < 300]  # Last 5 minutes
            
            # More anomalies means less stability
            anomaly_factor = max(0.0, 1.0 - (len(recent_anomalies) * 0.2))  # Each anomaly reduces by 0.2
            
            # Combine with other metrics
            stability_score = anomaly_factor  # For now, just use anomaly factor
            
            return max(0.0, min(1.0, stability_score))
            
        except Exception as e:
            logger.error(f"Error calculating presence stability: {e}")
            return 0.5  # Default middle value on error
    
    async def _enhance_vr_experience(self):
        """
        Enhance VR experience based on high sentience detection.
        This is called when sentience metrics cross above threshold.
        """
        if not self.event_bus:
            return
            
        try:
            # Publish enhancement request to VR system
            self.event_bus.publish("vr.experience.enhance", {
                "reason": "sentience_threshold",
                "enhancements": [
                    "increased_responsiveness",
                    "deeper_immersion",
                    "enhanced_visuals",
                    "spatial_audio_boost",
                    "haptic_feedback_intensity"
                ],
                "sentience_metrics": self.vr_sentience_metrics,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info("Enhanced VR experience due to high sentience detection")
            
        except Exception as e:
            logger.error(f"Error enhancing VR experience: {e}")
    
    async def _revert_vr_experience(self):
        """
        Revert VR experience to standard settings when sentience drops below threshold.
        """
        if not self.event_bus:
            return
            
        try:
            # Publish revert request to VR system
            self.event_bus.publish("vr.experience.revert", {
                "reason": "sentience_below_threshold",
                "sentience_metrics": self.vr_sentience_metrics,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info("Reverted VR experience to standard settings")
            
        except Exception as e:
            logger.error(f"Error reverting VR experience: {e}")
            
    async def get_sentience_history(self) -> List[Dict[str, Any]]:
        """Get the sentience detection history for VR system."""
        return self.sentience_history
    
    async def get_current_metrics(self) -> Dict[str, float]:
        """Get the current VR sentience metrics."""
        return self.vr_sentience_metrics.copy()
