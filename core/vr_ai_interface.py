#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
VR-AI Interface component for integrating VR with AI in Kingdom AI.
"""

import os
import logging
import json
import time
import copy
from datetime import datetime

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class VRAIInterface(BaseComponent):
    """
    Component for integrating VR with AI in Kingdom AI.
    Provides bidirectional communication between VR environment and AI systems.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the VR-AI Interface component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus, config)
        self.name = "VRAIInterface"
        self.description = "Integrates VR with AI systems for immersive interactions"
        
        # AI models integration configuration
        self.ai_models = self.config.get("ai_models", {
            "thoth": {
                "enabled": True,
                "priority": 1
            },
            "voice": {
                "enabled": True,
                "priority": 2
            },
            "intent": {
                "enabled": True,
                "priority": 3
            }
        })
        
        # VR gesture recognition settings
        self.gesture_recognition = self.config.get("gesture_recognition", {
            "enabled": True,
            "confidence_threshold": 0.75,
            "gestures": {
                "point": "SELECT",
                "grab": "INTERACT",
                "swipe": "NAVIGATE",
                "pinch": "ZOOM",
                "thumbs_up": "CONFIRM",
                "thumbs_down": "CANCEL",
                "palm_open": "MENU",
                "fist": "CLOSE"
            }
        })
        
        # Action mapping from VR to AI system
        self.action_mapping = self.config.get("action_mapping", {
            "SELECT": ["ai.focus", "gui.select"],
            "INTERACT": ["ai.interact", "trading.order"],
            "NAVIGATE": ["gui.navigate", "ai.context_switch"],
            "ZOOM": ["gui.zoom", "market.detail"],
            "CONFIRM": ["trading.confirm", "ai.execute"],
            "CANCEL": ["trading.cancel", "ai.abort"],
            "MENU": ["gui.menu", "ai.options"],
            "CLOSE": ["gui.close", "ai.reset"]
        })
        
        # Internal state
        self.active_ai_model = "thoth"
        self.last_gesture = None
        self.last_gesture_time = None
        self.last_ai_response = None
        self.last_ai_response_time = None
        self.vr_session_active = False
        self.ai_response_queue = []
        self.vr_tracking_data = {}
        self.interaction_history = []
        self.max_history_size = self.config.get("max_history_size", 100)
        self.design_specs = {}
        self.active_design_id = None
        self.grabs = {"left": None, "right": None}
        
        # Visualization settings
        self.visualization = self.config.get("visualization", {
            "ai_responses": {
                "location": "floating",
                "distance": 1.0,
                "size": 0.5,
                "follow_user": True
            },
            "market_data": {
                "location": "wall",
                "position": [0, 1.7, -3.0],
                "size": 3.0,
                "follow_user": False
            }
        })
        
    async def initialize(self):
        """Initialize the VR-AI Interface component."""
        logger.info("Initializing VR-AI Interface component")
        
        # Subscribe to VR events
        self.event_bus and self.event_bus.subscribe_sync("vr.session.started", self.on_vr_session_started)
        self.event_bus and self.event_bus.subscribe_sync("vr.session.ended", self.on_vr_session_ended)
        self.event_bus and self.event_bus.subscribe_sync("vr.tracking.update", self.on_vr_tracking_update)
        self.event_bus and self.event_bus.subscribe_sync("vr.interaction", self.on_vr_interaction)
        
        # Subscribe to AI events
        self.event_bus and self.event_bus.subscribe_sync("ai.response", self.on_ai_response)
        self.event_bus and self.event_bus.subscribe_sync("thoth.response", self.on_thoth_response)
        self.event_bus and self.event_bus.subscribe_sync("voice.response", self.on_voice_response)
        self.event_bus and self.event_bus.subscribe_sync("intent.recognized", self.on_intent_recognized)
        self.event_bus and self.event_bus.subscribe_sync("vr.brain.design_spec", self.on_brain_design_spec)
        self.event_bus and self.event_bus.subscribe_sync("vr.brain.update_visual", self.on_brain_update_visual)
        self.event_bus and self.event_bus.subscribe_sync("vr.brain.delete_visual", self.on_brain_delete_visual)
        self.event_bus and self.event_bus.subscribe_sync("vr.design.measure_request", self.on_design_measure_request)
        
        # System events
        self.event_bus and self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
        
        # AI-specific subscriptions
        self.event_bus and self.event_bus.subscribe_sync("ai.model.change", self.on_ai_model_change)
        
        # Market data subscriptions for VR visualization
        self.event_bus and self.event_bus.subscribe_sync("market.update", self.on_market_update)
        self.event_bus and self.event_bus.subscribe_sync("portfolio.update", self.on_portfolio_update)
        
        # Initialize interaction history
        self.interaction_history = []
        
        logger.info("VR-AI Interface component initialized")
        
        # Publish component status
        self.event_bus and self.event_bus.publish("vrai.status", {
            "status": "initialized",
            "active_ai_model": self.active_ai_model,
            "gesture_recognition": self.gesture_recognition["enabled"],
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_vr_session_started(self, data):
        """
        Handle VR session started event.
        
        Args:
            data: VR session data
        """
        session_id = data.get("session_id")
        environment = data.get("environment")
        
        logger.info(f"VR session started: {session_id} in environment {environment}")
        
        # Update internal state
        self.vr_session_active = True
        
        # Initialize tracking data
        self.vr_tracking_data = {}
        
        # Publish AI welcome message to VR
        welcome_message = {
            "type": "ai_response",
            "content": "Welcome to the Kingdom AI VR interface. How can I assist you today?",
            "source": self.active_ai_model,
            "visualization": self.visualization["ai_responses"],
            "timestamp": datetime.now().isoformat()
        }
        
        self.event_bus.publish("vr.command", {
            "command": "display_message",
            "message": welcome_message,
            "priority": "high"
        })
        
        # Notify AI of VR session
        self.event_bus.publish("ai.context", {
            "context_type": "vr_session",
            "session_id": session_id,
            "environment": environment,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_vr_session_ended(self, data):
        """
        Handle VR session ended event.
        
        Args:
            data: VR session data
        """
        session_id = data.get("session_id")
        duration = data.get("duration", 0)
        
        logger.info(f"VR session ended: {session_id}, duration: {duration}s")
        
        # Update internal state
        self.vr_session_active = False
        
        # Clear tracking data
        self.vr_tracking_data = {}
        
        # Save interaction history
        if self.interaction_history:
            await self.save_interaction_history(session_id)
            
            # Clear history
            self.interaction_history = []
        
        # Notify AI of VR session end
        self.event_bus.publish("ai.context", {
            "context_type": "vr_session_end",
            "session_id": session_id,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_vr_tracking_update(self, data):
        """
        Handle VR tracking update event.
        
        Args:
            data: VR tracking data
        """
        # Store tracking data
        self.vr_tracking_data = data
        
        # Check for gestures if enabled
        if self.gesture_recognition["enabled"]:
            recognized_gesture = await self.recognize_gesture(data)
            
            if recognized_gesture:
                self.last_gesture = recognized_gesture
                self.last_gesture_time = datetime.now()
                
                # Map gesture to action
                actions = self.action_mapping.get(recognized_gesture, [])
                
                # Execute actions
                await self.execute_actions(recognized_gesture, actions, data)
                
                # Add to interaction history
                self.add_to_interaction_history({
                    "type": "gesture",
                    "gesture": recognized_gesture,
                    "actions": actions,
                    "timestamp": datetime.now().isoformat()
                })
        await self._update_grabbed_designs(data)
    
    async def recognize_gesture(self, tracking_data):
        """
        Recognize gestures from VR tracking data.
        
        Args:
            tracking_data: VR tracking data
            
        Returns:
            str: Recognized gesture or None
        """
        if "left_hand" not in tracking_data or "right_hand" not in tracking_data:
            return None

        left_pos = tracking_data["left_hand"].get("position", [0, 0, 0])
        left_rot = tracking_data["left_hand"].get("rotation", [0, 0, 0])
        right_pos = tracking_data["right_hand"].get("position", [0, 0, 0])
        right_rot = tracking_data["right_hand"].get("rotation", [0, 0, 0])
        left_fingers = tracking_data["left_hand"].get("fingers", {})
        right_fingers = tracking_data["right_hand"].get("fingers", {})

        try:
            import requests as _req
            gesture_payload = {
                "left_pos": left_pos, "left_rot": left_rot,
                "right_pos": right_pos, "right_rot": right_rot,
                "left_fingers": left_fingers, "right_fingers": right_fingers,
            }
            prompt = (
                "Classify this VR hand gesture data into exactly one label: "
                "SELECT, GRAB, SWIPE_LEFT, SWIPE_RIGHT, SWIPE_UP, SWIPE_DOWN, "
                "PINCH, OPEN_HAND, THUMBS_UP, THUMBS_DOWN, CONFIRM, CANCEL, NONE. "
                f"Data: {json.dumps(gesture_payload)}. Reply with ONLY the label."
            )
            resp = _req.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3", "prompt": prompt, "stream": False},
                timeout=3
            )
            if resp.status_code == 200:
                label = resp.json().get("response", "").strip().upper()
                valid = {"SELECT", "GRAB", "SWIPE_LEFT", "SWIPE_RIGHT", "SWIPE_UP",
                         "SWIPE_DOWN", "PINCH", "OPEN_HAND", "THUMBS_UP",
                         "THUMBS_DOWN", "CONFIRM", "CANCEL", "NONE"}
                if label in valid and label != "NONE":
                    return label
        except Exception:
            pass

        if right_pos[2] < -0.5 and abs(right_rot[0]) < 0.2:
            return "SELECT"

        hand_dist = sum((r - l) ** 2 for r, l in zip(right_pos, left_pos)) ** 0.5
        if hand_dist < 0.1:
            return "PINCH"

        right_grip = right_fingers.get("grip_strength", 0)
        if right_grip > 0.8:
            return "GRAB"

        return None
    
    async def execute_actions(self, gesture, actions, data):
        """
        Execute actions based on recognized gesture.
        
        Args:
            gesture: Recognized gesture
            actions: List of actions to execute
            data: Tracking data
        """
        for action in actions:
            # Parse action type and target
            try:
                action_type, action_target = action.split(".")
            except ValueError:
                logger.error(f"Invalid action format: {action}")
                continue
                
            # Execute action based on type
            if action_type == "ai":
                # AI-related actions
                if action_target == "focus":
                    # Focus AI on user's point of interest
                    point_of_interest = self.calculate_point_of_interest(data)
                    
                    self.event_bus.publish("ai.focus", {
                        "point_of_interest": point_of_interest,
                        "source": "vr",
                        "gesture": gesture,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                elif action_target == "interact":
                    # Send interaction to AI
                    self.event_bus.publish("ai.interact", {
                        "action": "gesture_interact",
                        "gesture": gesture,
                        "source": "vr",
                        "timestamp": datetime.now().isoformat()
                    })
                    
                elif action_target == "execute":
                    # Execute current AI command
                    self.event_bus.publish("ai.execute", {
                        "action": "execute_command",
                        "source": "vr",
                        "gesture": gesture,
                        "timestamp": datetime.now().isoformat()
                    })
                    
            elif action_type == "gui":
                # GUI-related actions
                if action_target == "select":
                    # Select GUI element
                    point_of_interest = self.calculate_point_of_interest(data)
                    
                    self.event_bus.publish("gui.select", {
                        "point": point_of_interest,
                        "source": "vr",
                        "gesture": gesture,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                elif action_target == "navigate":
                    # Navigate GUI
                    self.event_bus.publish("gui.navigate", {
                        "direction": self.calculate_swipe_direction(data),
                        "source": "vr",
                        "gesture": gesture,
                        "timestamp": datetime.now().isoformat()
                    })
                    
            elif action_type == "trading":
                if action_target == "order":
                    order_params = self._build_vr_trading_order(gesture, data)
                    self.event_bus.publish("trading.order.submit", order_params)
                    self.event_bus.publish("trading.action", {
                        "action": "order_submitted",
                        "order": order_params,
                        "source": "vr",
                        "gesture": gesture,
                        "timestamp": datetime.now().isoformat()
                    })
    
    def calculate_point_of_interest(self, data):
        """
        Calculate point of interest based on VR data.
        
        Args:
            data: VR tracking data
            
        Returns:
            list: 3D point coordinates
        """
        # Simple ray casting from right hand
        if "right_hand" not in data:
            return [0, 0, -3]  # Default forward direction
            
        hand_pos = data["right_hand"].get("position", [0, 0, 0])
        hand_rot = data["right_hand"].get("rotation", [0, 0, 0])
        
        # Simple forward projection
        # In a real implementation, this would use proper ray casting
        direction = [0, 0, -1]  # Forward direction
        
        # Distance to project
        distance = 3.0
        
        # Calculate point of interest
        point = [
            hand_pos[0] + direction[0] * distance,
            hand_pos[1] + direction[1] * distance,
            hand_pos[2] + direction[2] * distance
        ]
        
        return point
    
    def calculate_swipe_direction(self, data):
        """
        Calculate swipe direction based on hand movement velocity.
        
        Args:
            data: VR tracking data
            
        Returns:
            str: Swipe direction
        """
        velocity = data.get("right_hand", {}).get("velocity", [0, 0, 0])
        vx, vy, vz = velocity if len(velocity) >= 3 else (0, 0, 0)

        abs_vals = {"left": -vx, "right": vx, "up": vy, "down": -vy}
        best = max(abs_vals, key=abs_vals.get)
        if abs_vals[best] > 0.3:
            return best
        return "right"

    def _build_vr_trading_order(self, gesture, data):
        """Build a trading order from VR gesture context."""
        vr_context = data.get("trading_context", {})
        side = "buy" if gesture in ("THUMBS_UP", "SWIPE_UP", "CONFIRM") else "sell"
        return {
            "symbol": vr_context.get("symbol", "BTC/USDT"),
            "side": side,
            "type": vr_context.get("order_type", "market"),
            "amount": vr_context.get("amount", 0.001),
            "source": "vr_gesture",
            "gesture": gesture,
            "timestamp": datetime.now().isoformat()
        }
    
    async def on_vr_interaction(self, data):
        """
        Handle VR interaction event.
        
        Args:
            data: VR interaction data
        """
        device_id = data.get("device_id")
        action = data.get("action")
        
        logger.info(f"VR interaction from {device_id}: {action}")
        
        # Add to interaction history
        self.add_to_interaction_history({
            "type": "interaction",
            "device_id": device_id,
            "action": action,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        
        # Process interaction
        await self.process_vr_interaction(data)
    
    async def process_vr_interaction(self, data):
        """
        Process VR interaction and forward to AI system.
        
        Args:
            data: VR interaction data
        """
        action = data.get("action")
        if not action:
            return
        object_id = data.get("object_id")
        if object_id:
            self.active_design_id = object_id
        interaction_type = data.get("interaction_type")
        hand = data.get("hand") or data.get("controller")
        if action in ("grab_start", "grab") or interaction_type in ("grab_start", "grab"):
            await self._start_grab(hand or "right", object_id)
        elif action in ("grab_end", "release") or interaction_type in ("grab_end", "release"):
            await self._end_grab(hand or "right")
        elif action in ("duplicate", "duplicate_object", "duplicate_image"):
            await self._duplicate_active_design()
        self.event_bus.publish("ai.input", {
            "type": "vr_interaction",
            "action": action,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        
        # Handle specific interactions
        if action == "voice_command":
            # Voice command from VR
            command = data.get("command")
            
            if command:
                # Apply direct design rotations for commands like "rotate", "turn", "spin"
                await self._apply_voice_design_command(command)
                self.event_bus.publish("voice.input", {
                    "command": command,
                    "source": "vr",
                    "timestamp": datetime.now().isoformat()
                })
                
        elif action == "object_interaction":
            # Object interaction in VR
            object_id = data.get("object_id")
            interaction_type = data.get("interaction_type")
            
            if object_id and interaction_type:
                # Map to system action
                if interaction_type == "select":
                    # Handle object selection
                    self.event_bus.publish("system.object.select", {
                        "object_id": object_id,
                        "source": "vr",
                        "timestamp": datetime.now().isoformat()
                    })
                    
                elif interaction_type == "interact":
                    # Handle object interaction
                    self.event_bus.publish("system.object.interact", {
                        "object_id": object_id,
                        "source": "vr",
                        "timestamp": datetime.now().isoformat()
                    })

    async def _apply_voice_design_command(self, command: str):
        text = command.lower()
        design_id = self.active_design_id
        if not design_id:
            return
        spec = self.design_specs.get(design_id)
        if not isinstance(spec, dict) or not spec:
            return
        if any(word in text for word in ["duplicate", "copy", "clone"]):
            await self._duplicate_active_design()
            return
        if not any(word in text for word in ["rotate", "turn", "spin", "twist"]):
            return
        angle = 0.0
        tokens = text.replace("degrees", "").split()
        for token in tokens:
            try:
                angle = float(token)
                break
            except ValueError:
                continue
        if angle <= 0.0:
            angle = 15.0
        axis = "y"
        sign = 1.0
        if "left" in text:
            axis = "y"
            sign = -1.0
        elif "right" in text:
            axis = "y"
            sign = 1.0
        elif "up" in text:
            axis = "x"
            sign = 1.0
        elif "down" in text:
            axis = "x"
            sign = -1.0
        elif "clockwise" in text:
            axis = "y"
            sign = -1.0
        elif "counterclockwise" in text or "anti-clockwise" in text or "anticlockwise" in text:
            axis = "y"
            sign = 1.0
        rotation = spec.get("rotation") or {"x": 0.0, "y": 0.0, "z": 0.0}
        new_rotation = {
            "x": float(rotation.get("x", 0.0)),
            "y": float(rotation.get("y", 0.0)),
            "z": float(rotation.get("z", 0.0))
        }
        new_rotation[axis] = float(new_rotation.get(axis, 0.0)) + sign * angle
        spec["rotation"] = new_rotation
        await self._publish_design_update(design_id, spec)

    async def _update_two_hand_scale(self, tracking_data, left_state, right_state):
        design_id = left_state.get("design_id")
        base_spec = left_state.get("base_spec")
        if not design_id or not isinstance(base_spec, dict) or not base_spec:
            return
        left_start = left_state.get("start_pos") or [0, 0, 0]
        right_start = right_state.get("start_pos") or [0, 0, 0]
        start_dx = float(right_start[0]) - float(left_start[0])
        start_dy = float(right_start[1]) - float(left_start[1])
        start_dz = float(right_start[2]) - float(left_start[2])
        start_dist = (start_dx ** 2 + start_dy ** 2 + start_dz ** 2) ** 0.5
        if start_dist <= 1e-4:
            return
        left_now = (tracking_data.get("left_hand") or {}).get("position", [0, 0, 0])
        right_now = (tracking_data.get("right_hand") or {}).get("position", [0, 0, 0])
        now_dx = float(right_now[0]) - float(left_now[0])
        now_dy = float(right_now[1]) - float(left_now[1])
        now_dz = float(right_now[2]) - float(left_now[2])
        now_dist = (now_dx ** 2 + now_dy ** 2 + now_dz ** 2) ** 0.5
        if now_dist <= 1e-4:
            return
        scale = now_dist / start_dist
        if scale <= 0.1:
            scale = 0.1
        if scale >= 5.0:
            scale = 5.0
        spec = copy.deepcopy(base_spec)
        components = spec.get("components")
        if isinstance(components, list):
            for comp in components:
                if not isinstance(comp, dict):
                    continue
                dims = comp.get("dimensions")
                if not isinstance(dims, dict):
                    continue
                shape = comp.get("shape")
                if shape == "cube":
                    for key in ("x", "y", "z"):
                        if key in dims:
                            try:
                                dims[key] = float(dims[key]) * scale
                            except Exception:
                                continue
                elif shape == "cylinder":
                    for key in ("r", "h"):
                        if key in dims:
                            try:
                                dims[key] = float(dims[key]) * scale
                            except Exception:
                                continue
                elif shape == "sphere":
                    if "r" in dims:
                        try:
                            dims["r"] = float(dims["r"]) * scale
                        except Exception:
                            pass
        await self._publish_design_update(design_id, spec)

    async def on_brain_design_spec(self, data):
        spec = data.get("spec") or data.get("design") or {}
        if not isinstance(spec, dict) or not spec:
            return
        design_id = data.get("design_id") or spec.get("id")
        if not design_id:
            return
        self.design_specs[design_id] = spec
        self.active_design_id = design_id
        self.event_bus and self.event_bus.publish("vr.design.state", {
            "design_id": design_id,
            "spec": spec,
            "source": "vr_ai_interface",
            "timestamp": datetime.now().isoformat()
        })

    async def on_brain_update_visual(self, data):
        design_id = data.get("component_id")
        properties = data.get("properties") or {}
        spec = properties.get("design_spec")
        if design_id and isinstance(spec, dict) and spec:
            self.design_specs[design_id] = spec
            self.active_design_id = design_id
            self.event_bus and self.event_bus.publish("vr.design.state", {
                "design_id": design_id,
                "spec": spec,
                "source": "vr_ai_interface",
                "timestamp": datetime.now().isoformat()
            })

    async def on_brain_delete_visual(self, data):
        design_id = data.get("component_id") or data.get("design_id")
        if not design_id:
            return
        if design_id in self.design_specs:
            del self.design_specs[design_id]
        if self.active_design_id == design_id:
            self.active_design_id = None

    async def _start_grab(self, hand, design_id):
        if not design_id:
            design_id = self.active_design_id
        if not design_id:
            return
        spec = self.design_specs.get(design_id)
        if not isinstance(spec, dict) or not spec:
            return
        tracking_hand = None
        if hand == "left":
            tracking_hand = self.vr_tracking_data.get("left_hand") or {}
        else:
            tracking_hand = self.vr_tracking_data.get("right_hand") or {}
        pos = tracking_hand.get("position", [0, 0, 0])
        rot = tracking_hand.get("rotation", [0, 0, 0])
        self.grabs["left" if hand == "left" else "right"] = {
            "design_id": design_id,
            "start_pos": list(pos),
            "start_rot": list(rot),
            "base_spec": copy.deepcopy(spec)
        }

    async def _end_grab(self, hand):
        key = "left" if hand == "left" else "right"
        self.grabs[key] = None

    async def _update_grabbed_designs(self, tracking_data):
        left_state = self.grabs.get("left")
        right_state = self.grabs.get("right")
        if left_state and right_state and left_state.get("design_id") and left_state.get("design_id") == right_state.get("design_id"):
            await self._update_two_hand_scale(tracking_data, left_state, right_state)
        else:
            if left_state:
                await self._update_single_hand_grab("left", tracking_data, left_state)
            if right_state:
                await self._update_single_hand_grab("right", tracking_data, right_state)

    async def _update_single_hand_grab(self, hand, tracking_data, state):
        design_id = state.get("design_id")
        base_spec = state.get("base_spec")
        start_pos = state.get("start_pos") or [0, 0, 0]
        start_rot = state.get("start_rot") or [0, 0, 0]
        if not design_id or not isinstance(base_spec, dict):
            return
        tracking_hand = None
        if hand == "left":
            tracking_hand = tracking_data.get("left_hand") or {}
        else:
            tracking_hand = tracking_data.get("right_hand") or {}
        pos = tracking_hand.get("position", [0, 0, 0])
        rot = tracking_hand.get("rotation", [0, 0, 0])
        dx = float(pos[0]) - float(start_pos[0])
        dy = float(pos[1]) - float(start_pos[1])
        dz = float(pos[2]) - float(start_pos[2])
        drx = float(rot[0]) - float(start_rot[0])
        dry = float(rot[1]) - float(start_rot[1])
        drz = float(rot[2]) - float(start_rot[2])
        spec = copy.deepcopy(base_spec)
        base_position = spec.get("position") or {"x": 0.0, "y": 1.7, "z": -2.0}
        new_position = {
            "x": float(base_position.get("x", 0.0)) + dx,
            "y": float(base_position.get("y", 0.0)) + dy,
            "z": float(base_position.get("z", 0.0)) + dz
        }
        spec["position"] = new_position
        base_rotation = spec.get("rotation") or {"x": 0.0, "y": 0.0, "z": 0.0}
        new_rotation = {
            "x": float(base_rotation.get("x", 0.0)) + drx,
            "y": float(base_rotation.get("y", 0.0)) + dry,
            "z": float(base_rotation.get("z", 0.0)) + drz
        }
        spec["rotation"] = new_rotation
        await self._publish_design_update(design_id, spec)

    async def _duplicate_active_design(self):
        design_id = self.active_design_id
        if not design_id:
            return
        base_spec = self.design_specs.get(design_id)
        if not isinstance(base_spec, dict) or not base_spec:
            return
        spec = copy.deepcopy(base_spec)
        original_id = spec.get("id") or design_id
        timestamp_suffix = int(time.time() * 1000)
        new_id = f"{original_id}_copy_{timestamp_suffix}"
        spec["id"] = new_id
        position = spec.get("position") or {"x": 0.0, "y": 1.7, "z": -2.0}
        spec["position"] = {
            "x": float(position.get("x", 0.0)) + 0.5,
            "y": float(position.get("y", 0.0)),
            "z": float(position.get("z", 0.0))
        }
        self.design_specs[new_id] = spec
        self.active_design_id = new_id
        self.event_bus and self.event_bus.publish("vr.brain.design_spec", {
            "design_id": new_id,
            "spec": spec,
            "source": "vr_ai_interface",
            "timestamp": datetime.now().isoformat()
        })

    async def _publish_design_update(self, design_id, spec):
        self.design_specs[design_id] = spec
        self.active_design_id = design_id
        if self.event_bus:
            self.event_bus.publish("vr.brain.update_visual", {
                "component_id": design_id,
                "properties": {
                    "design_spec": spec,
                    "position": spec.get("position"),
                    "updated_at": datetime.now().isoformat()
                }
            })
            self.event_bus.publish("vr.design.state", {
                "design_id": design_id,
                "spec": spec,
                "source": "vr_ai_interface",
                "timestamp": datetime.now().isoformat()
            })
    
    async def on_ai_response(self, data):
        """
        Handle AI response event.
        
        Args:
            data: AI response data
        """
        response_type = data.get("type", "text")
        content = data.get("content")
        
        if not content:
            return
            
        logger.info(f"AI response received: {response_type}")
        
        # Store response
        self.last_ai_response = content
        self.last_ai_response_time = datetime.now()
        
        # Add to queue
        self.ai_response_queue.append({
            "type": response_type,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Send to VR if session active
        if self.vr_session_active:
            await self.send_ai_response_to_vr(response_type, content)
            
        # Add to interaction history
        self.add_to_interaction_history({
            "type": "ai_response",
            "response_type": response_type,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_thoth_response(self, data):
        """
        Handle Thoth AI response event.
        
        Args:
            data: Thoth response data
        """
        # Forward to general AI response handler
        await self.on_ai_response({
            "type": "text",
            "content": data.get("response"),
            "source": "thoth"
        })
    
    async def on_voice_response(self, data):
        """
        Handle voice system response event.
        
        Args:
            data: Voice response data
        """
        # Forward to general AI response handler
        await self.on_ai_response({
            "type": "voice",
            "content": data.get("response"),
            "source": "voice"
        })
    
    async def on_intent_recognized(self, data):
        """
        Handle intent recognition event.
        
        Args:
            data: Intent data
        """
        intent = data.get("intent")
        confidence = data.get("confidence", 0)
        
        logger.info(f"Intent recognized: {intent} (confidence: {confidence})")
        
        # Add to interaction history
        self.add_to_interaction_history({
            "type": "intent",
            "intent": intent,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })
        
        # Process intent if confidence is high enough
        if confidence >= self.gesture_recognition["confidence_threshold"]:
            # Map intent to actions
            if intent == "select":
                actions = self.action_mapping.get("SELECT", [])
            elif intent == "interact":
                actions = self.action_mapping.get("INTERACT", [])
            elif intent == "navigate":
                actions = self.action_mapping.get("NAVIGATE", [])
            else:
                # No mapping
                return
                
            # Execute actions
            await self.execute_actions(intent, actions, self.vr_tracking_data)
    
    async def on_design_measure_request(self, data):
        """Handle vr.design.measure_request and summarize design measurements.
        
        This computes an axis-aligned bounding box for the active design and
        returns per-component dimensions so higher-level AI can answer
        questions like "how big is this?" with exact values in meters.
        """
        try:
            query = (data or {}).get("query") if isinstance(data, dict) else None
            design_id = None
            if isinstance(data, dict):
                design_id = data.get("design_id") or data.get("component_id")
            if not design_id:
                design_id = self.active_design_id
            if not design_id:
                return

            spec = self.design_specs.get(design_id)
            if not isinstance(spec, dict) or not spec:
                return

            units = spec.get("units", "meters")
            components = spec.get("components") or []
            if not isinstance(components, list) or not components:
                return

            min_x = min_y = min_z = None
            max_x = max_y = max_z = None
            summary_components = []

            for comp in components:
                if not isinstance(comp, dict):
                    continue
                shape = comp.get("shape") or "unknown"
                dims = comp.get("dimensions") or {}
                pos = comp.get("position") or {}

                try:
                    cx = float(pos.get("x", 0.0))
                    cy = float(pos.get("y", 0.0))
                    cz = float(pos.get("z", 0.0))
                except Exception:
                    cx = cy = cz = 0.0

                half_x = half_y = half_z = 0.0
                try:
                    if shape == "cube":
                        dx = float(dims.get("x", 0.0))
                        dy = float(dims.get("y", 0.0))
                        dz = float(dims.get("z", 0.0))
                        half_x, half_y, half_z = dx / 2.0, dy / 2.0, dz / 2.0
                    elif shape == "cylinder":
                        r = float(dims.get("r", 0.0))
                        h = float(dims.get("h", 0.0))
                        half_x = half_z = r
                        half_y = h / 2.0
                    elif shape == "sphere":
                        r = float(dims.get("r", 0.0))
                        half_x = half_y = half_z = r
                except Exception:
                    half_x = half_y = half_z = 0.0

                if any(v != 0.0 for v in (half_x, half_y, half_z)):
                    c_min_x = cx - half_x
                    c_max_x = cx + half_x
                    c_min_y = cy - half_y
                    c_max_y = cy + half_y
                    c_min_z = cz - half_z
                    c_max_z = cz + half_z

                    if min_x is None or c_min_x < min_x:
                        min_x = c_min_x
                    if max_x is None or c_max_x > max_x:
                        max_x = c_max_x
                    if min_y is None or c_min_y < min_y:
                        min_y = c_min_y
                    if max_y is None or c_max_y > max_y:
                        max_y = c_max_y
                    if min_z is None or c_min_z < min_z:
                        min_z = c_min_z
                    if max_z is None or c_max_z > max_z:
                        max_z = c_max_z

                dim_summary = {}
                for key, value in (dims.items() if isinstance(dims, dict) else []):
                    try:
                        dim_summary[key] = float(value)
                    except Exception:
                        continue

                summary_components.append({
                    "id": comp.get("id"),
                    "name": comp.get("name"),
                    "shape": shape,
                    "dimensions": dim_summary,
                })

            overall_bbox = None
            if min_x is not None and max_x is not None and min_y is not None and max_y is not None and min_z is not None and max_z is not None:
                width = float(max_x - min_x)
                height = float(max_y - min_y)
                depth = float(max_z - min_z)
                overall_bbox = {
                    "min": {"x": float(min_x), "y": float(min_y), "z": float(min_z)},
                    "max": {"x": float(max_x), "y": float(max_y), "z": float(max_z)},
                    "width": width,
                    "height": height,
                    "depth": depth,
                }

            summary = {
                "design_id": design_id,
                "name": spec.get("name"),
                "units": units,
                "overall_bbox": overall_bbox,
                "components": summary_components,
            }

            if self.event_bus:
                self.event_bus.publish("vr.design.measure_response", {
                    "design_id": design_id,
                    "summary": summary,
                    "query": query,
                    "source": "vr_ai_interface",
                    "timestamp": datetime.now().isoformat(),
                })
        except Exception as e:
            logger.error(f"Error handling vr.design.measure_request: {e}")
    
    async def send_ai_response_to_vr(self, response_type, content):
        """
        Send AI response to VR system.
        
        Args:
            response_type: Type of response
            content: Response content
        """
        visualization_settings = self.visualization["ai_responses"]
        
        message = {
            "type": "ai_response",
            "response_type": response_type,
            "content": content,
            "source": self.active_ai_model,
            "visualization": visualization_settings,
            "timestamp": datetime.now().isoformat()
        }
        
        self.event_bus.publish("vr.command", {
            "command": "display_message",
            "message": message,
            "priority": "normal"
        })
    
    async def on_market_update(self, data):
        """
        Handle market update event.
        
        Args:
            data: Market update data
        """
        # Only process if VR session is active
        if not self.vr_session_active:
            return
            
        # Prepare market data visualization
        visualization_settings = self.visualization["market_data"]
        
        message = {
            "type": "market_data",
            "data": data,
            "visualization": visualization_settings,
            "timestamp": datetime.now().isoformat()
        }
        
        self.event_bus.publish("vr.command", {
            "command": "update_visualization",
            "visualization_id": "market_data",
            "data": message,
            "priority": "low"
        })
    
    async def on_portfolio_update(self, data):
        """
        Handle portfolio update event.
        
        Args:
            data: Portfolio update data
        """
        # Only process if VR session is active
        if not self.vr_session_active:
            return
            
        # Prepare portfolio data visualization
        visualization_settings = self.visualization["market_data"]
        
        message = {
            "type": "portfolio_data",
            "data": data,
            "visualization": visualization_settings,
            "timestamp": datetime.now().isoformat()
        }
        
        self.event_bus.publish("vr.command", {
            "command": "update_visualization",
            "visualization_id": "portfolio_data",
            "data": message,
            "priority": "low"
        })
    
    async def on_ai_model_change(self, data):
        """
        Handle AI model change event.
        
        Args:
            data: AI model change data
        """
        model = data.get("model")
        
        if not model or model not in self.ai_models:
            return
            
        logger.info(f"Changing active AI model to {model}")
        
        # Update active model
        self.active_ai_model = model
        
        # Publish status update
        self.event_bus.publish("vrai.status", {
            "status": "model_changed",
            "active_ai_model": model,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_to_interaction_history(self, interaction):
        """
        Add interaction to history.
        
        Args:
            interaction: Interaction data
        """
        # Add to history
        self.interaction_history.append(interaction)
        
        # Trim history if needed
        if len(self.interaction_history) > self.max_history_size:
            self.interaction_history = self.interaction_history[-self.max_history_size:]
    
    async def save_interaction_history(self, session_id):
        """
        Save interaction history to file.
        
        Args:
            session_id: VR session ID
        """
        if not self.interaction_history:
            return
            
        try:
            # Create directory if not exists
            history_dir = os.path.join(self.config.get("data_dir", "data"), "vr_history")
            os.makedirs(history_dir, exist_ok=True)
            
            # Save to file
            filename = f"{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(history_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump({
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "interactions": self.interaction_history
                }, f, indent=2)
                
            logger.info(f"Saved VR interaction history to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving interaction history: {str(e)}")
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the VR-AI Interface component."""
        logger.info("Shutting down VR-AI Interface component")
        
        # Save any pending interaction history
        if self.vr_session_active and self.interaction_history:
            await self.save_interaction_history(f"shutdown_{int(time.time())}")
        
        logger.info("VR-AI Interface component shut down successfully")
