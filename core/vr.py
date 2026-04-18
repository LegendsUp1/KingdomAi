"""VR System module for Kingdom AI.

SOTA 2026: Full integration with Creation Engine, Genie 3 World Model, and Vision Stream.
"""
from typing import Any, Dict, Optional, List
import asyncio
import time
import json
from core.base_component import BaseComponent
from core.event_bus import EventBus

# SOTA 2026: Genie 3 World Model integration
try:
    from core.genie3_world_model import (
        Genie3WorldModel, WorldConfig, WorldType, QualityLevel, ActionType,
        get_genie3_world_model
    )
    HAS_GENIE3 = True
except (ImportError, Exception) as e:
    # Handle both ImportError and any internal dependency errors
    HAS_GENIE3 = False
    get_genie3_world_model = None
    Genie3WorldModel = None
    WorldConfig = None
    WorldType = None
    QualityLevel = None
    ActionType = None
    import logging
    logging.getLogger(__name__).warning(f"⚠️ Genie 3 World Model not available: {e}")

# SOTA 2026: Redis for Creation Engine communication
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


class VRSystem(BaseComponent):
    """Virtual Reality system for immersive trading.
    
    SOTA 2026 Integration:
    - Genie 3 World Model for procedural world generation
    - Creation Engine for image/video generation
    - Vision Stream for real-world input
    - Full bidirectional event flow
    """
    
    # Redis Creation Engine channels
    CREATION_REQUEST_CHANNEL = 'creation.request'
    CREATION_RESPONSE_CHANNEL = 'creation.response'
    WORLD_REQUEST_CHANNEL = 'genie3.world.request'
    WORLD_RESPONSE_CHANNEL = 'genie3.world.response'
    
    def __init__(self, event_bus: EventBus) -> None:
        """Initialize VR system.
        
        Args:
            event_bus: Event bus instance
        """
        super().__init__("VRSystem", event_bus)
        self.resolution = (1920, 1080)
        self.frame_rate = 60
        self._initialized = False
        
        # SOTA 2026: Genie 3 World Model integration
        self._genie3_model: Optional[Any] = None
        self._current_world = None
        self._world_cache: Dict[str, Any] = {}
        
        # SOTA 2026: Creation Engine Redis client
        self._redis_client = None
        self._creation_requests: Dict[str, Dict] = {}
        
        # SOTA 2026: Vision Stream integration
        self._latest_vision_frame = None
        self._vision_frame_timestamp = 0
        self._vision_to_world_enabled = False
        
    @property
    def initialized(self) -> bool:
        return self._initialized
        
    @initialized.setter
    def initialized(self, value: bool) -> None:
        self._initialized = value
        
    async def initialize(self, event_bus=None, config=None) -> bool:
        """Initialize the VR system.
        
        SOTA 2026: Full integration with Genie 3, Creation Engine, and Vision Stream.
        
        Args:
            event_bus: Optional EventBus instance to use for initialization
            config: Optional configuration to use for initialization
            
        Returns:
            bool: Success status
        """
        # Call the parent initialize method first
        await super().initialize(event_bus, config)
        
        try:
            await self._init_renderer()
            await self._init_scene()
            
            # SOTA 2026: Initialize Genie 3 World Model
            await self._init_genie3()
            
            # SOTA 2026: Initialize Creation Engine connection
            await self._init_creation_engine()
            
            # SOTA 2026: Subscribe to all integration events
            self._subscribe_to_integration_events()
            
            self.initialized = True
            if self.event_bus:
                self.event_bus.publish("vr.status", {
                    "status": "initialized",
                    "genie3_available": self._genie3_model is not None,
                    "creation_engine_connected": self._redis_client is not None
                })
            return True
        except Exception as e:
            if self.event_bus:
                self.event_bus.publish("vr.error", {
                    "error": str(e),
                    "source": "VRSystem.initialize"
                })
            return False
    
    async def _init_genie3(self) -> None:
        """SOTA 2026: Initialize Genie 3 World Model for procedural world generation."""
        if not HAS_GENIE3:
            self.logger.info("Genie 3 World Model not available")
            return
        
        try:
            self._genie3_model = get_genie3_world_model()
            if self._genie3_model:
                # Connect event bus to Genie 3
                self._genie3_model.event_bus = self.event_bus
                
                if not self._genie3_model.initialized:
                    await self._genie3_model.initialize()
                
                self.logger.info("🌍 Genie 3 World Model connected to VR System")
                
                if self.event_bus:
                    self.event_bus.publish("vr.genie3.connected", {
                        "status": "connected",
                        "initialized": self._genie3_model.initialized
                    })
        except Exception as e:
            self.logger.warning(f"Failed to initialize Genie 3: {e}")
            self._genie3_model = None
    
    async def _init_creation_engine(self) -> None:
        """SOTA 2026: Initialize connection to Creation Engine via Redis."""
        if not HAS_REDIS:
            self.logger.info("Redis not available for Creation Engine connection")
            return
        
        try:
            self._redis_client = redis.Redis(
                host='localhost',
                port=6380,
                password='QuantumNexus2025',
                decode_responses=True
            )
            self._redis_client.ping()
            self.logger.info("🎨 Creation Engine connected via Redis")
            
            if self.event_bus:
                self.event_bus.publish("vr.creation_engine.connected", {
                    "status": "connected",
                    "host": "localhost",
                    "port": 6380
                })
        except Exception as e:
            self.logger.warning(f"Failed to connect to Creation Engine: {e}")
            self._redis_client = None
    
    def _subscribe_to_integration_events(self) -> None:
        """SOTA 2026: Subscribe to all integration events for full data flow."""
        if not self.event_bus:
            return
        
        # Vision Stream events
        self.event_bus.subscribe("vision.stream.frame", self._handle_vision_frame)
        self.event_bus.subscribe("vision.stream.status", self._handle_vision_status)
        
        # Genie 3 events
        self.event_bus.subscribe("genie3.generation.complete", self._handle_world_generated)
        self.event_bus.subscribe("genie3.world.step", self._handle_world_step)
        self.event_bus.subscribe("genie3.world.state", self._handle_world_state)
        
        # Creation Engine events
        self.event_bus.subscribe("creation.response", self._handle_creation_response)
        self.event_bus.subscribe("creation.progress", self._handle_creation_progress)
        
        # VR-specific command events
        self.event_bus.subscribe("vr.generate_world", self._handle_generate_world_request)
        self.event_bus.subscribe("vr.create_image", self._handle_create_image_request)
        self.event_bus.subscribe("vr.vision_to_world", self._handle_vision_to_world_request)
        
        self.logger.info("✅ VR System subscribed to all integration events")
    
    async def _handle_vision_frame(self, data: Dict[str, Any]) -> None:
        """SOTA 2026: Handle incoming vision stream frames."""
        self._latest_vision_frame = data.get("frame")
        self._vision_frame_timestamp = data.get("timestamp", time.time())
        
        # If vision-to-world mode is enabled, process frame for world generation
        if self._vision_to_world_enabled and self._latest_vision_frame is not None:
            await self._process_vision_for_world()
    
    async def _handle_vision_status(self, data: Dict[str, Any]) -> None:
        """Handle vision stream status updates."""
        if self.event_bus:
            self.event_bus.publish("vr.vision.status", {
                "vision_active": data.get("active", False),
                "vision_url": data.get("url")
            })
    
    async def _handle_world_generated(self, data: Dict[str, Any]) -> None:
        """SOTA 2026: Handle world generation completion from Genie 3."""
        world_id = data.get("world_id")
        if world_id and self._genie3_model:
            # Cache the world for VR rendering
            self._current_world = self._genie3_model.current_world
            self._world_cache[world_id] = self._current_world
            
            if self.event_bus:
                self.event_bus.publish("vr.world.loaded", {
                    "world_id": world_id,
                    "frame_count": data.get("frame_count", 0),
                    "ready_for_rendering": True
                })
    
    async def _handle_world_step(self, data: Dict[str, Any]) -> None:
        """Handle world step updates - sync VR view with world state."""
        world_id = data.get("world_id")
        frame_index = data.get("frame_index", 0)
        
        if self.event_bus:
            self.event_bus.publish("vr.world.frame_update", {
                "world_id": world_id,
                "frame_index": frame_index,
                "action": data.get("action")
            })
    
    async def _handle_world_state(self, data: Dict[str, Any]) -> None:
        """Sync VR camera with world state position/rotation."""
        if "main" in self._scene.get("cameras", {}):
            self._scene["cameras"]["main"]["position"] = list(data.get("position", (0, 5, 10)))
            # Convert rotation to camera orientation
            rotation = data.get("rotation", (0, 0, 0))
            self._scene["cameras"]["main"]["rotation"] = list(rotation)
            self._scene_dirty = True
    
    async def _handle_creation_response(self, data: Dict[str, Any]) -> None:
        """Handle creation engine response."""
        request_id = data.get("request_id")
        if request_id in self._creation_requests:
            original_request = self._creation_requests.pop(request_id)
            
            if self.event_bus:
                self.event_bus.publish("vr.creation.complete", {
                    "request_id": request_id,
                    "status": data.get("status"),
                    "image_path": data.get("image_path"),
                    "original_prompt": original_request.get("prompt")
                })
    
    async def _handle_creation_progress(self, data: Dict[str, Any]) -> None:
        """Handle creation progress updates."""
        if self.event_bus:
            self.event_bus.publish("vr.creation.progress", {
                "request_id": data.get("request_id"),
                "progress": data.get("progress", 0),
                "status": data.get("status")
            })
    
    async def _handle_generate_world_request(self, data: Dict[str, Any]) -> None:
        """SOTA 2026: Handle VR world generation request."""
        prompt = data.get("prompt", "A beautiful trading floor environment")
        world_type = data.get("world_type", "simulation")
        quality = data.get("quality", "high")
        
        await self.generate_world(prompt, world_type, quality)
    
    async def _handle_create_image_request(self, data: Dict[str, Any]) -> None:
        """Handle VR image creation request via Creation Engine."""
        prompt = data.get("prompt")
        if prompt:
            await self.request_creation(prompt)
    
    async def _handle_vision_to_world_request(self, data: Dict[str, Any]) -> None:
        """Enable/disable vision-to-world generation mode."""
        self._vision_to_world_enabled = data.get("enabled", False)
        
        if self.event_bus:
            self.event_bus.publish("vr.vision_to_world.status", {
                "enabled": self._vision_to_world_enabled
            })
    
    async def _process_vision_for_world(self) -> None:
        """Process vision frame for world generation context."""
        # Rate limit to avoid overwhelming the system
        if not hasattr(self, '_last_vision_process') or \
           time.time() - self._last_vision_process > 5.0:  # Process every 5 seconds
            self._last_vision_process = time.time()
            
            if self.event_bus:
                self.event_bus.publish("vr.vision.processing", {
                    "timestamp": self._vision_frame_timestamp,
                    "for_world_generation": True
                })
            
    async def _init_renderer(self) -> None:
        """Initialize the VR renderer with SOTA 2026 configuration."""
        # SOTA 2026: Initialize renderer configuration for trading visualization
        self._renderer_config = {
            "backend": "webgl",  # WebGL for cross-platform compatibility
            "antialias": True,
            "alpha": True,
            "preserve_drawing_buffer": True,
            "power_preference": "high-performance",
            "resolution_scale": 1.0,
            "max_fps": self.frame_rate,
            "shadows_enabled": True,
            "post_processing": {
                "bloom": True,
                "ambient_occlusion": True,
                "depth_of_field": False,
            }
        }
        self._render_targets = {}
        self._shader_cache = {}
        self._texture_cache = {}
        self.logger.info(f"VR Renderer initialized at {self.resolution[0]}x{self.resolution[1]} @ {self.frame_rate}fps")
        
    async def _init_scene(self) -> None:
        """Initialize the VR scene with SOTA 2026 trading environment."""
        # SOTA 2026: Create immersive trading scene
        self._scene = {
            "objects": {},
            "lights": {
                "ambient": {"color": "#1a1a2e", "intensity": 0.3},
                "directional": {"color": "#ffffff", "intensity": 0.8, "position": [10, 20, 10]},
                "point_lights": []
            },
            "cameras": {
                "main": {"fov": 75, "near": 0.1, "far": 1000, "position": [0, 5, 10]}
            },
            "environment": {
                "skybox": "trading_floor",
                "fog": {"enabled": True, "color": "#0a0a14", "density": 0.01}
            },
            "trading_elements": {
                "price_charts": [],
                "order_books": [],
                "portfolio_displays": [],
                "market_tickers": [],
                "alert_zones": []
            }
        }
        self._scene_dirty = False
        self.logger.info("VR Scene initialized with trading environment")
        
    async def update_scene(self, data: Dict[str, Any]) -> None:
        """Update the VR scene with new data.
        
        Args:
            data: Scene update data
        """
        try:
            if not self.initialized:
                await self.initialize()
            
            # SOTA 2026: Process scene updates based on data type
            update_type = data.get("type", "generic")
            
            if update_type == "price_update":
                # Update price visualization in VR space
                symbol = data.get("symbol", "BTC")
                price = data.get("price", 0.0)
                if "price_charts" in self._scene.get("trading_elements", {}):
                    self._scene["trading_elements"]["price_charts"].append({
                        "symbol": symbol,
                        "price": price,
                        "timestamp": data.get("timestamp")
                    })
                    # Keep last 1000 points for performance
                    self._scene["trading_elements"]["price_charts"] = \
                        self._scene["trading_elements"]["price_charts"][-1000:]
                        
            elif update_type == "order_book":
                # Update 3D order book visualization
                self._scene["trading_elements"]["order_books"] = data.get("order_book", [])
                
            elif update_type == "portfolio":
                # Update portfolio display
                self._scene["trading_elements"]["portfolio_displays"] = data.get("positions", [])
                
            elif update_type == "alert":
                # Trigger visual alert in VR space
                alert = {
                    "message": data.get("message", "Alert"),
                    "severity": data.get("severity", "info"),
                    "position": data.get("position", [0, 2, -3])
                }
                self._scene["trading_elements"]["alert_zones"].append(alert)
                
            self._scene_dirty = True
            
            if self.event_bus:
                self.event_bus.publish("vr.scene.updated", {
                    "data": data,
                    "scene_elements": len(self._scene.get("objects", {}))
                })
            
        except Exception as e:
            if self.event_bus:
                self.event_bus.publish("vr.error", {
                    "error": str(e),
                    "source": "VRSystem.update_scene"
                })
    
    def get_scene_state(self) -> Dict[str, Any]:
        """Get current VR scene state for synchronization."""
        return {
            "initialized": self.initialized,
            "resolution": self.resolution,
            "frame_rate": self.frame_rate,
            "scene": self._scene if hasattr(self, '_scene') else {},
            "renderer_config": self._renderer_config if hasattr(self, '_renderer_config') else {},
            "genie3_available": self._genie3_model is not None,
            "creation_engine_connected": self._redis_client is not None,
            "current_world_id": self._current_world.world_id if self._current_world else None,
            "vision_to_world_enabled": self._vision_to_world_enabled
        }
    
    # ========== SOTA 2026: Genie 3 World Generation ==========
    
    async def generate_world(
        self,
        prompt: str,
        world_type: str = "simulation",
        quality: str = "high",
        initial_image=None
    ) -> Optional[Any]:
        """
        SOTA 2026: Generate an interactive 3D world using Genie 3.
        
        Args:
            prompt: Text description of the world to generate
            world_type: Type of world (game_world, simulation, architectural, nature, urban, fantasy)
            quality: Quality level (draft, medium, high, ultra)
            initial_image: Optional image to initialize world from
            
        Returns:
            Generated world object or None
        """
        if not self._genie3_model:
            self.logger.warning("Genie 3 not available for world generation")
            if self.event_bus:
                self.event_bus.publish("vr.world.error", {
                    "error": "Genie 3 World Model not available",
                    "prompt": prompt
                })
            return None
        
        try:
            if self.event_bus:
                self.event_bus.publish("vr.world.generating", {
                    "prompt": prompt,
                    "world_type": world_type,
                    "quality": quality
                })
            
            # Convert string types to enums if Genie 3 is available
            if HAS_GENIE3:
                wt = WorldType(world_type) if world_type in [e.value for e in WorldType] else WorldType.SIMULATION
                ql = QualityLevel(quality) if quality in [e.value for e in QualityLevel] else QualityLevel.HIGH
            else:
                wt = world_type
                ql = quality
            
            # Generate world
            world = await self._genie3_model.generate_world_from_prompt(
                prompt=prompt,
                world_type=wt,
                quality=ql,
                initial_image=initial_image
            )
            
            if world:
                self._current_world = world
                self._world_cache[world.world_id] = world
                
                if self.event_bus:
                    self.event_bus.publish("vr.world.ready", {
                        "world_id": world.world_id,
                        "prompt": prompt,
                        "frame_count": len(world.frames)
                    })
                
                self.logger.info(f"🌍 World generated: {world.world_id}")
                return world
            
            return None
            
        except Exception as e:
            self.logger.error(f"World generation failed: {e}")
            if self.event_bus:
                self.event_bus.publish("vr.world.error", {
                    "error": str(e),
                    "prompt": prompt
                })
            return None
    
    async def step_world(self, action: str) -> Optional[Any]:
        """
        SOTA 2026: Step the current world with an action.
        
        Args:
            action: Action to take (move_forward, turn_left, etc.)
            
        Returns:
            New frame or None
        """
        if not self._genie3_model or not self._current_world:
            return None
        
        try:
            # Convert action string to enum
            if HAS_GENIE3:
                action_type = ActionType(action) if action in [e.value for e in ActionType] else ActionType.IDLE
            else:
                action_type = action
            
            new_frame = await self._genie3_model.step_world(action_type, self._current_world)
            
            if self.event_bus:
                self.event_bus.publish("vr.world.stepped", {
                    "world_id": self._current_world.world_id,
                    "action": action,
                    "frame_index": self._current_world.state.frame_index if self._current_world.state else 0
                })
            
            return new_frame
            
        except Exception as e:
            self.logger.error(f"World step failed: {e}")
            return None
    
    async def export_world(self, format: str = "video", output_path: str = None) -> Optional[str]:
        """Export current world to various formats."""
        if not self._genie3_model or not self._current_world:
            return None
        
        try:
            path = await self._genie3_model.export_world(
                self._current_world,
                format=format,
                output_path=output_path
            )
            
            if self.event_bus and path:
                self.event_bus.publish("vr.world.exported", {
                    "world_id": self._current_world.world_id,
                    "format": format,
                    "path": path
                })
            
            return path
            
        except Exception as e:
            self.logger.error(f"World export failed: {e}")
            return None
    
    # ========== SOTA 2026: Creation Engine Integration ==========
    
    async def request_creation(
        self,
        prompt: str,
        mode: str = "image",
        options: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        SOTA 2026: Request creation from Creation Engine.
        
        Args:
            prompt: Creation prompt
            mode: Mode (image, video, world, genie3_world)
            options: Additional options
            
        Returns:
            Request ID or None
        """
        if not self._redis_client:
            self.logger.warning("Creation Engine not connected")
            if self.event_bus:
                self.event_bus.publish("vr.creation.error", {
                    "error": "Creation Engine not connected",
                    "prompt": prompt
                })
            return None
        
        try:
            import uuid
            request_id = str(uuid.uuid4())
            
            request = {
                "request_id": request_id,
                "prompt": prompt,
                "mode": mode,
                "options": options or {},
                "timestamp": time.time()
            }
            
            # Track request
            self._creation_requests[request_id] = request
            
            # Determine channel based on mode
            if mode in ["world", "genie3_world"]:
                channel = self.WORLD_REQUEST_CHANNEL
            else:
                channel = self.CREATION_REQUEST_CHANNEL
            
            # Publish request
            self._redis_client.publish(channel, json.dumps(request))
            
            if self.event_bus:
                self.event_bus.publish("vr.creation.requested", {
                    "request_id": request_id,
                    "prompt": prompt,
                    "mode": mode
                })
            
            self.logger.info(f"🎨 Creation requested: {request_id}")
            return request_id
            
        except Exception as e:
            self.logger.error(f"Creation request failed: {e}")
            return None
    
    # ========== SOTA 2026: Vision Stream Integration ==========
    
    async def generate_world_from_vision(self, prompt_enhancement: str = "") -> Optional[Any]:
        """
        SOTA 2026: Generate a world using the current vision stream frame.
        
        Args:
            prompt_enhancement: Additional prompt to enhance the vision-based generation
            
        Returns:
            Generated world or None
        """
        if self._latest_vision_frame is None:
            self.logger.warning("No vision frame available")
            return None
        
        prompt = "A 3D world based on this camera view"
        if prompt_enhancement:
            prompt = f"{prompt}. {prompt_enhancement}"
        
        return await self.generate_world(
            prompt=prompt,
            world_type="simulation",
            quality="high",
            initial_image=self._latest_vision_frame
        )
    
    def enable_vision_to_world(self, enabled: bool = True) -> None:
        """Enable/disable automatic vision-to-world generation."""
        self._vision_to_world_enabled = enabled
        
        if self.event_bus:
            self.event_bus.publish("vr.vision_to_world.status", {
                "enabled": enabled
            })
            
    async def cleanup(self) -> bool:
        """Clean up VR resources.
        
        Returns:
            bool: Success status
        """
        try:
            # SOTA 2026: Properly clean up all VR resources
            if hasattr(self, '_render_targets'):
                self._render_targets.clear()
            if hasattr(self, '_shader_cache'):
                self._shader_cache.clear()
            if hasattr(self, '_texture_cache'):
                self._texture_cache.clear()
            if hasattr(self, '_scene'):
                self._scene = {}
                
            self.initialized = False
            if self.event_bus:
                self.event_bus.publish("vr.status", {
                    "status": "shutdown"
                })
            self.logger.info("VR System cleaned up successfully")
            return True
        except Exception as e:
            if self.event_bus:
                self.event_bus.publish("vr.error", {
                    "error": str(e),
                    "source": "VRSystem.cleanup"
                })
            return False
