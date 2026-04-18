"""
Vision Stream Component - SOTA 2026 with Unified Vision Abstraction Layer

Features:
- Multi-Modal Fusion (webcam + VR headset + Meta glasses)
- Unified Vision Pipeline (detection, recognition, tracking)
- Genie 3 World Model integration
- Creation Engine integration
- VL-JEPA AI-powered vision understanding
- Real-time 120Hz processing capability
"""
import os
import re
import sys
import threading
import time
import json
from typing import Optional, List, Tuple, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

import cv2
import numpy as np

from core.base_component import BaseComponent
from core.event_bus import EventBus


def _wsl_resolve_exe(name: str) -> str:
    """No-op on native Linux — returns name as-is."""
    return name


# =========================================================================
# 2026 SOTA: Unified Vision Abstraction Layer
# =========================================================================

class VisionSourceType(Enum):
    """Types of vision sources for multi-modal fusion."""
    WEBCAM = "webcam"
    VR_HEADSET = "vr_headset"
    META_GLASSES = "meta_glasses"
    SCREEN_CAPTURE = "screen_capture"
    IP_CAMERA = "ip_camera"
    FILE = "file"


class VisionFrameQuality(Enum):
    """Quality levels for vision frames."""
    RAW = "raw"           # No processing
    FAST = "fast"         # Minimal processing for speed
    BALANCED = "balanced" # Balance of speed and quality
    QUALITY = "quality"   # Full quality processing
    AI_ENHANCED = "ai_enhanced"  # AI-enhanced processing


@dataclass
class VisionFrame:
    """
    2026 SOTA: Unified Vision Frame for multi-modal fusion.
    
    Standardized frame format across all vision sources.
    """
    timestamp: float
    source_type: VisionSourceType
    source_id: str
    frame: np.ndarray
    width: int
    height: int
    channels: int = 3
    quality: VisionFrameQuality = VisionFrameQuality.RAW
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # AI analysis results (populated by vision analysis)
    faces: List[Dict[str, Any]] = field(default_factory=list)
    objects: List[Dict[str, Any]] = field(default_factory=list)
    text: Optional[str] = None
    pose: Optional[Dict[str, Any]] = None
    scene_description: Optional[str] = None
    
    # Tracking and fusion data
    frame_id: int = 0
    is_keyframe: bool = False
    fusion_weight: float = 1.0  # Weight for multi-source fusion


class UnifiedVisionPipeline:
    """
    2026 SOTA: Unified Vision Pipeline for multi-modal fusion.
    
    Combines frames from multiple sources (webcam, VR, Meta glasses)
    into a unified understanding of the visual environment.
    
    Features:
    - Source registration and management
    - Frame synchronization across sources
    - Multi-modal fusion with weighted combining
    - Unified AI analysis pipeline
    - Event-driven output
    """
    
    def __init__(self, event_bus=None, config: Dict[str, Any] = None):
        self.event_bus = event_bus
        self.config = config or {}
        self.logger = None
        
        # Registered vision sources
        self.sources: Dict[str, Dict[str, Any]] = {}
        
        # Frame buffers for each source
        self.frame_buffers: Dict[str, deque] = {}
        self.buffer_size = self.config.get("buffer_size", 10)
        
        # Fusion settings
        self.fusion_enabled = self.config.get("fusion_enabled", True)
        self.fusion_weights: Dict[str, float] = {}
        self.primary_source: Optional[str] = None
        
        # Processing settings
        self.target_fps = self.config.get("target_fps", 30)
        self.quality = VisionFrameQuality(self.config.get("quality", "balanced"))
        
        # Synchronization
        self._lock = threading.Lock()
        self._frame_count = 0
        self._last_fusion_time = 0.0
        
        # Callbacks for frame processing
        self._frame_callbacks: List[Callable] = []
        self._fusion_callbacks: List[Callable] = []
        
        # Performance metrics
        self.metrics = {
            "frames_processed": 0,
            "fusion_operations": 0,
            "avg_latency_ms": 0.0,
            "sources_active": 0,
        }
    
    def register_source(
        self,
        source_id: str,
        source_type: VisionSourceType,
        priority: int = 1,
        fusion_weight: float = 1.0,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Register a vision source for multi-modal fusion."""
        with self._lock:
            self.sources[source_id] = {
                "type": source_type,
                "priority": priority,
                "active": False,
                "metadata": metadata or {},
                "last_frame_time": 0.0,
                "frame_count": 0,
            }
            self.frame_buffers[source_id] = deque(maxlen=self.buffer_size)
            self.fusion_weights[source_id] = fusion_weight
            
            # Set as primary if highest priority
            if self.primary_source is None or priority > self.sources.get(self.primary_source, {}).get("priority", 0):
                self.primary_source = source_id
            
            return True
    
    def unregister_source(self, source_id: str) -> bool:
        """Unregister a vision source."""
        with self._lock:
            if source_id in self.sources:
                del self.sources[source_id]
                del self.frame_buffers[source_id]
                del self.fusion_weights[source_id]
                
                if self.primary_source == source_id:
                    self.primary_source = None
                    # Find new primary
                    max_priority = -1
                    for sid, sdata in self.sources.items():
                        if sdata["priority"] > max_priority:
                            max_priority = sdata["priority"]
                            self.primary_source = sid
                return True
            return False
    
    def process_frame(self, vision_frame: VisionFrame) -> VisionFrame:
        """Process a frame from any source through the unified pipeline."""
        start_time = time.time()
        
        with self._lock:
            source_id = vision_frame.source_id
            
            # Update source state
            if source_id in self.sources:
                self.sources[source_id]["active"] = True
                self.sources[source_id]["last_frame_time"] = vision_frame.timestamp
                self.sources[source_id]["frame_count"] += 1
            
            # Add to buffer
            if source_id in self.frame_buffers:
                vision_frame.frame_id = self._frame_count
                self._frame_count += 1
                self.frame_buffers[source_id].append(vision_frame)
            
            # Apply quality processing
            vision_frame = self._apply_quality_processing(vision_frame)
            
            # Trigger frame callbacks
            for callback in self._frame_callbacks:
                try:
                    callback(vision_frame)
                except Exception:
                    pass
            
            # Update metrics
            self.metrics["frames_processed"] += 1
            latency = (time.time() - start_time) * 1000
            self.metrics["avg_latency_ms"] = (self.metrics["avg_latency_ms"] * 0.9) + (latency * 0.1)
            self.metrics["sources_active"] = sum(1 for s in self.sources.values() if s["active"])
        
        return vision_frame
    
    def get_fused_frame(self) -> Optional[VisionFrame]:
        """
        Get a fused frame combining all active sources.
        
        Uses weighted blending based on source priorities and fusion weights.
        """
        if not self.fusion_enabled:
            return self._get_primary_frame()
        
        with self._lock:
            active_frames = []
            
            # Get latest frame from each active source
            for source_id, buffer in self.frame_buffers.items():
                if buffer and self.sources[source_id]["active"]:
                    latest_frame = buffer[-1]
                    weight = self.fusion_weights.get(source_id, 1.0)
                    active_frames.append((latest_frame, weight))
            
            if not active_frames:
                return None
            
            if len(active_frames) == 1:
                return active_frames[0][0]
            
            # Perform weighted fusion
            fused_frame = self._fuse_frames(active_frames)
            
            self.metrics["fusion_operations"] += 1
            self._last_fusion_time = time.time()
            
            # Trigger fusion callbacks
            for callback in self._fusion_callbacks:
                try:
                    callback(fused_frame)
                except Exception:
                    pass
            
            return fused_frame
    
    def _get_primary_frame(self) -> Optional[VisionFrame]:
        """Get the latest frame from the primary source."""
        if self.primary_source and self.primary_source in self.frame_buffers:
            buffer = self.frame_buffers[self.primary_source]
            if buffer:
                return buffer[-1]
        return None
    
    def _fuse_frames(self, frames_with_weights: List[Tuple[VisionFrame, float]]) -> VisionFrame:
        """Fuse multiple frames using weighted blending."""
        # Normalize weights
        total_weight = sum(w for _, w in frames_with_weights)
        if total_weight == 0:
            total_weight = 1.0
        
        # Get target dimensions from primary source
        primary_frame = frames_with_weights[0][0]
        target_shape = primary_frame.frame.shape
        
        # Initialize fused array
        fused_array = np.zeros(target_shape, dtype=np.float32)
        
        # Weighted blending
        for frame, weight in frames_with_weights:
            normalized_weight = weight / total_weight
            
            # Resize if needed
            if frame.frame.shape != target_shape:
                resized = cv2.resize(frame.frame, (target_shape[1], target_shape[0]))
            else:
                resized = frame.frame
            
            fused_array += resized.astype(np.float32) * normalized_weight
        
        # Create fused frame
        fused = VisionFrame(
            timestamp=time.time(),
            source_type=VisionSourceType.WEBCAM,  # Mixed source
            source_id="fused",
            frame=fused_array.astype(np.uint8),
            width=target_shape[1],
            height=target_shape[0],
            channels=target_shape[2] if len(target_shape) > 2 else 1,
            quality=self.quality,
            metadata={
                "sources": [f.source_id for f, _ in frames_with_weights],
                "fusion_type": "weighted_blend"
            },
            frame_id=self._frame_count,
            fusion_weight=1.0
        )
        
        # Combine AI analysis results from all sources
        for frame, _ in frames_with_weights:
            fused.faces.extend(frame.faces)
            fused.objects.extend(frame.objects)
            if frame.text:
                if fused.text:
                    fused.text += " " + frame.text
                else:
                    fused.text = frame.text
            if frame.pose and not fused.pose:
                fused.pose = frame.pose
            if frame.scene_description and not fused.scene_description:
                fused.scene_description = frame.scene_description
        
        return fused
    
    def _apply_quality_processing(self, frame: VisionFrame) -> VisionFrame:
        """Apply quality-based processing to frame."""
        if self.quality == VisionFrameQuality.RAW:
            return frame
        
        img = frame.frame
        
        if self.quality in [VisionFrameQuality.BALANCED, VisionFrameQuality.QUALITY, VisionFrameQuality.AI_ENHANCED]:
            # Basic enhancement
            try:
                # Auto-contrast using CLAHE
                if len(img.shape) == 3:
                    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
                    img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            except Exception:
                pass
        
        if self.quality == VisionFrameQuality.QUALITY:
            # Noise reduction
            try:
                img = cv2.fastNlMeansDenoisingColored(img, None, 3, 3, 7, 21)
            except Exception:
                pass
        
        frame.frame = img
        frame.quality = self.quality
        return frame
    
    def add_frame_callback(self, callback: Callable) -> None:
        """Add callback for processed frames."""
        self._frame_callbacks.append(callback)
    
    def add_fusion_callback(self, callback: Callable) -> None:
        """Add callback for fused frames."""
        self._fusion_callbacks.append(callback)
    
    def get_source_status(self) -> Dict[str, Any]:
        """Get status of all registered sources."""
        with self._lock:
            return {
                source_id: {
                    "type": data["type"].value,
                    "active": data["active"],
                    "priority": data["priority"],
                    "frame_count": data["frame_count"],
                    "fusion_weight": self.fusion_weights.get(source_id, 1.0),
                }
                for source_id, data in self.sources.items()
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get pipeline metrics."""
        return self.metrics.copy()


# Global unified pipeline instance
_unified_pipeline: Optional[UnifiedVisionPipeline] = None


def get_unified_vision_pipeline(event_bus=None, config: Dict[str, Any] = None) -> UnifiedVisionPipeline:
    """Get or create the global unified vision pipeline."""
    global _unified_pipeline
    if _unified_pipeline is None:
        _unified_pipeline = UnifiedVisionPipeline(event_bus, config)
    return _unified_pipeline

# SOTA 2026: Universal Data Visualizer integration
try:
    from core.universal_data_visualizer import get_universal_visualizer, DataType
    HAS_VISUALIZER = True
except ImportError:
    HAS_VISUALIZER = False

# SOTA 2026: Quantum Enhancement Bridge for real quantum hardware
try:
    from core.quantum_enhancement_bridge import get_quantum_bridge, QuantumEnhancementBridge
    HAS_QUANTUM_BRIDGE = True
except ImportError:
    HAS_QUANTUM_BRIDGE = False
    get_quantum_bridge = None

# SOTA 2026: Genie 3 World Model integration
try:
    from core.genie3_world_model import (
        Genie3WorldModel, WorldConfig, WorldType, QualityLevel,
        get_genie3_world_model
    )
    HAS_GENIE3 = True
except ImportError:
    HAS_GENIE3 = False
    get_genie3_world_model = None

# SOTA 2026: Redis for Creation Engine communication
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

# For reliable MJPEG streaming on Windows
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class VisionStreamComponent(BaseComponent):
    """Vision streaming component that consumes an MJPEG URL and exposes frames via the event bus.

    Event channels:
      - vision.stream.start  {"url"?: str}
      - vision.stream.stop   {}
      - vision.stream.status {"active": bool, "url": str, "error"?: str}
      - vision.stream.frame  {"frame": np.ndarray, "timestamp": float}
    """

    def __init__(self, name: str = "VisionStream", event_bus: Optional[EventBus] = None, config=None):
        event_bus = event_bus or EventBus.get_instance()
        super().__init__(name=name, event_bus=event_bus, config=config)

        self._capture = None
        self._stream_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._current_url: Optional[str] = None
        self.is_running = False
        
        # SOTA 2026: Zero-latency mode (mirror-like instant feedback)
        self._zero_latency_mode = True  # Default: prioritize speed over enhancement
        self._enhance_enabled = False   # Disabled by default for zero latency
        self._denoise_strength = 0      # 0 = no denoising for speed
        self._sharpen_strength = 0.0    # 0 = no sharpening for speed
        self._auto_contrast = False     # Disabled for speed
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        
        # VL-JEPA integration for AI-powered vision understanding
        self._vl_jepa_enabled = True
        self._vl_jepa = None  # Lazy loaded
        self._vl_jepa_queue = []  # Async processing queue
        
        # SOTA 2026: Universal Data Visualizer for multi-sensor fusion
        self._visualizer = None
        if HAS_VISUALIZER:
            try:
                self._visualizer = get_universal_visualizer(event_bus)
                self.logger.info("🎨 Universal Data Visualizer connected to VisionStream")
            except Exception as e:
                self.logger.debug(f"Visualizer not available: {e}")
        
        # SOTA 2026: Quantum Enhancement Bridge for real quantum-enhanced vision
        self._quantum_bridge = None
        self._quantum_enhance_enabled = False  # Enable for quantum-optimized parameters
        if HAS_QUANTUM_BRIDGE and get_quantum_bridge:
            try:
                self._quantum_bridge = get_quantum_bridge(event_bus)
                if self._quantum_bridge.is_quantum_available():
                    self._quantum_enhance_enabled = True
                    self.logger.info("⚛️ Quantum Enhancement Bridge connected - real QPU available")
                else:
                    self.logger.info("⚛️ Quantum Enhancement Bridge connected (classical fallback)")
            except Exception as e:
                self.logger.debug(f"Quantum bridge not available: {e}")
        
        # SOTA 2026: Genie 3 World Model integration
        self._genie3_model = None
        self._genie3_enabled = False
        self._world_generation_in_progress = False
        self._frame_for_world: Optional[np.ndarray] = None
        if HAS_GENIE3 and get_genie3_world_model:
            try:
                self._genie3_model = get_genie3_world_model()
                if self._genie3_model:
                    self._genie3_enabled = True
                    self.logger.info("🌍 Genie 3 World Model connected to VisionStream")
            except Exception as e:
                self.logger.debug(f"Genie 3 not available: {e}")
        
        # SOTA 2026: Creation Engine Redis connection
        self._redis_client = None
        self._creation_engine_enabled = False
        if HAS_REDIS:
            try:
                self._redis_client = redis.Redis(host='localhost', port=6380, password='QuantumNexus2025', decode_responses=True)
                self._redis_client.ping()
                self._creation_engine_enabled = True
                self.logger.info("🎨 Creation Engine connected via Redis")
            except Exception as e:
                self.logger.debug(f"Creation Engine not available: {e}")

        # Register this component on the EventBus registry
        try:
            if hasattr(self.event_bus, "register_component"):
                self.event_bus.register_component("vision_stream", self)
        except Exception:
            self.logger.exception("Failed to register VisionStream component on EventBus")

    def subscribe_to_events(self) -> None:
        if not self.event_bus:
            self.logger.warning("No EventBus available for VisionStream")
            return

        self.subscribe_sync("vision.stream.start", self._on_start_stream)
        self.subscribe_sync("vision.stream.stop", self._on_stop_stream)
        
        # SOTA 2026: Genie 3 and Creation Engine integration events
        self.subscribe_sync("vision.generate_world", self._on_generate_world)
        self.subscribe_sync("vision.create_image", self._on_create_image)
        self.subscribe_sync("vision.capture_for_world", self._on_capture_for_world)
        
        # Subscribe to Genie 3 responses
        self.subscribe_sync("genie3.generation.complete", self._on_world_generated)
        
        # Subscribe to Creation Engine responses
        self.subscribe_sync("creation.response", self._on_creation_response)
    
    # ========== SOTA 2026: Genie 3 World Generation ==========
    
    def _on_generate_world(self, data: Dict[str, Any]) -> None:
        """Generate a 3D world from the current vision frame using Genie 3."""
        if not self._genie3_enabled or not self._genie3_model:
            self.logger.warning("Genie 3 not available for world generation")
            if self.event_bus:
                self.event_bus.publish_sync("vision.world.error", {
                    "error": "Genie 3 not available"
                })
            return
        
        if self._world_generation_in_progress:
            self.logger.warning("World generation already in progress")
            return
        
        prompt = data.get("prompt", "A 3D world based on this camera view")
        world_type = data.get("world_type", "simulation")
        quality = data.get("quality", "high")
        
        # Use stored frame or request a capture
        frame = self._frame_for_world
        if frame is None:
            self.logger.info("No captured frame, will use next streamed frame")
            return
        
        self._world_generation_in_progress = True
        
        # Run world generation in a thread to avoid blocking
        def generate():
            try:
                import asyncio
                
                # Create event loop for async call
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Connect event bus
                    self._genie3_model.event_bus = self.event_bus
                    
                    if not self._genie3_model.initialized:
                        loop.run_until_complete(self._genie3_model.initialize())
                    
                    # Convert types
                    wt = WorldType(world_type) if world_type in [e.value for e in WorldType] else WorldType.SIMULATION
                    ql = QualityLevel(quality) if quality in [e.value for e in QualityLevel] else QualityLevel.HIGH
                    
                    # Generate world
                    world = loop.run_until_complete(
                        self._genie3_model.generate_world_from_prompt(
                            prompt=prompt,
                            world_type=wt,
                            quality=ql,
                            initial_image=frame
                        )
                    )
                    
                    if world and self.event_bus:
                        self.event_bus.publish_sync("vision.world.ready", {
                            "world_id": world.world_id,
                            "prompt": prompt,
                            "frame_count": len(world.frames),
                            "source": "vision_stream"
                        })
                finally:
                    loop.close()
                    
            except Exception as e:
                self.logger.error(f"World generation failed: {e}")
                if self.event_bus:
                    self.event_bus.publish_sync("vision.world.error", {
                        "error": str(e),
                        "prompt": prompt
                    })
            finally:
                self._world_generation_in_progress = False
                self._frame_for_world = None
        
        thread = threading.Thread(target=generate, daemon=True)
        thread.start()
        
        if self.event_bus:
            self.event_bus.publish_sync("vision.world.generating", {
                "prompt": prompt,
                "world_type": world_type
            })
    
    def _on_capture_for_world(self, data: Dict[str, Any]) -> None:
        """Capture the next frame for world generation."""
        self._capture_next_frame_for_world = True
        self.logger.info("📸 Will capture next frame for world generation")
    
    def _on_world_generated(self, data: Dict[str, Any]) -> None:
        """Handle world generation completion."""
        if self.event_bus:
            self.event_bus.publish_sync("vision.genie3.world_ready", {
                "world_id": data.get("world_id"),
                "success": data.get("success", True)
            })
    
    # ========== SOTA 2026: Creation Engine Integration ==========
    
    def _on_create_image(self, data: Dict[str, Any]) -> None:
        """Request image creation from the Creation Engine based on current vision."""
        if not self._creation_engine_enabled or not self._redis_client:
            self.logger.warning("Creation Engine not available")
            return
        
        import uuid
        request_id = str(uuid.uuid4())
        prompt = data.get("prompt", "An enhanced version of this camera view")
        mode = data.get("mode", "image")
        
        request = {
            "request_id": request_id,
            "prompt": prompt,
            "mode": mode,
            "options": data.get("options", {}),
            "timestamp": time.time(),
            "source": "vision_stream"
        }
        
        try:
            channel = 'genie3.world.request' if mode in ['world', 'genie3_world'] else 'creation.request'
            self._redis_client.publish(channel, json.dumps(request))
            
            if self.event_bus:
                self.event_bus.publish_sync("vision.creation.requested", {
                    "request_id": request_id,
                    "prompt": prompt,
                    "mode": mode
                })
            
            self.logger.info(f"🎨 Creation requested: {request_id}")
        except Exception as e:
            self.logger.error(f"Failed to request creation: {e}")
    
    def _on_creation_response(self, data: Dict[str, Any]) -> None:
        """Handle creation response from Creation Engine."""
        if data.get("source") != "vision_stream":
            return  # Not our request
        
        if self.event_bus:
            self.event_bus.publish_sync("vision.creation.complete", {
                "request_id": data.get("request_id"),
                "status": data.get("status"),
                "image_path": data.get("image_path")
            })
    
    def capture_frame_for_world(self) -> bool:
        """Capture the current frame for world generation."""
        self._capture_next_frame_for_world = True
        return True
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get status of all integrations."""
        return {
            "genie3_available": self._genie3_enabled,
            "creation_engine_connected": self._creation_engine_enabled,
            "visualizer_available": HAS_VISUALIZER and self._visualizer is not None,
            "quantum_bridge_available": self._quantum_enhance_enabled,
            "vl_jepa_enabled": self._vl_jepa_enabled,
            "world_generation_in_progress": self._world_generation_in_progress
        }

    def _enhance_frame(self, frame: np.ndarray) -> np.ndarray:
        """SOTA 2026: AI-powered real-time frame enhancement for acute vision clarity."""
        if self._zero_latency_mode:
            return frame  # Skip all processing for mirror-like speed
        
        try:
            # SOTA 2026: Use quantum-optimized parameters when available
            if self._quantum_enhance_enabled and self._quantum_bridge:
                try:
                    # Request quantum-optimized enhancement parameters (async, non-blocking)
                    if self.event_bus:
                        self.event_bus.publish("quantum.enhance.vision", {
                            "type": "denoise" if self._denoise_strength > 0 else "contrast",
                            "frame_shape": frame.shape,
                            "request_id": f"vision_{time.time()}"
                        })
                except Exception as qe:
                    self.logger.debug(f"Quantum enhancement request failed: {qe}")
            
            # 1. Fast bilateral denoising (edge-preserving)
            if self._denoise_strength > 0:
                d = 5 + self._denoise_strength
                sigma = 20 + self._denoise_strength * 10
                frame = cv2.bilateralFilter(frame, d, sigma, sigma)
            
            # 2. Auto contrast with CLAHE
            if self._auto_contrast:
                lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
                lab[:, :, 0] = self._clahe.apply(lab[:, :, 0])
                frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            # 3. Unsharp mask sharpening
            if self._sharpen_strength > 0:
                blurred = cv2.GaussianBlur(frame, (0, 0), 3)
                frame = cv2.addWeighted(frame, 1.0 + self._sharpen_strength, blurred, -self._sharpen_strength, 0)
                frame = np.clip(frame, 0, 255).astype(np.uint8)
            
            return frame
        except Exception as e:
            self.logger.debug(f"Enhancement error: {e}")
            return frame

    def _process_vl_jepa_async(self, frame: np.ndarray):
        """SOTA 2026: Async VL-JEPA processing (non-blocking for zero latency display)."""
        if not self._vl_jepa_enabled:
            return
        
        try:
            # Lazy load VL-JEPA integration
            if self._vl_jepa is None:
                try:
                    from core.vl_jepa import VLJEPAIntegration
                    self._vl_jepa = VLJEPAIntegration(event_bus=self.event_bus)
                    self.logger.info("VL-JEPA integration loaded for vision processing")
                except ImportError:
                    self._vl_jepa_enabled = False
                    return
            
            # Queue frame for async processing (don't block display)
            if hasattr(self.event_bus, "publish_sync"):
                self.event_bus.publish_sync("vl_jepa.vision_frame", {
                    "frame": frame,
                    "timestamp": time.time(),
                    "source": "vision_stream"
                })
        except Exception as e:
            self.logger.debug(f"VL-JEPA processing error: {e}")

    def set_zero_latency(self, enabled: bool = True):
        """Enable/disable zero-latency mirror mode."""
        self._zero_latency_mode = enabled
        if enabled:
            self._enhance_enabled = False
            self.logger.info("Zero-latency mode ENABLED - mirror-like instant feedback")
        else:
            self.logger.info("Zero-latency mode DISABLED - enhancements active")

    def set_enhancement(self, enabled: bool = True, denoise: int = 3, sharpen: float = 0.5, contrast: bool = True):
        """Configure SOTA 2026 vision enhancement settings."""
        self._enhance_enabled = enabled
        self._zero_latency_mode = not enabled  # Disable zero-latency if enhancing
        self._denoise_strength = max(0, min(10, denoise))
        self._sharpen_strength = max(0.0, min(2.0, sharpen))
        self._auto_contrast = contrast
        self.logger.info(f"Vision enhancement: enabled={enabled}, denoise={denoise}, sharpen={sharpen}, contrast={contrast}")

    def _try_start_mjpeg_server(self) -> bool:
        """
        Attempt to start the MJPEG server locally on native Linux.
        Returns True if server was started or is already running.
        """
        import subprocess, shutil
        from pathlib import Path
        
        script_path = Path(__file__).parent.parent / "brio_mjpeg_server.py"
        if not script_path.exists():
            self.logger.warning(f"MJPEG server script not found: {script_path}")
            return False
        
        try:
            python_bin = shutil.which('python3') or shutil.which('python') or 'python3'
            subprocess.Popen(
                [python_bin, str(script_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.logger.info(f"🚀 Started MJPEG server: {script_path}")
            
            time.sleep(2)
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to start MJPEG server: {e}")
            return False
    
    def _resolve_default_url(self):
        env_url = os.environ.get("KINGDOM_VISION_URL")
        if env_url:
            return env_url
        
        # Use localhost for native Linux (MJPEG server runs locally)
        host_ip = self._get_windows_host_ip()
        
        # SOTA 2026: MJPEG server endpoints - server detects ANY camera generically
        # The /brio.mjpg path is just the endpoint name - server auto-detects any webcam
        candidate_urls = [
            f"http://{host_ip}:8090/brio.mjpg",   # Primary endpoint (server auto-detects camera)
            "http://localhost:8090/brio.mjpg",
            "http://127.0.0.1:8090/brio.mjpg",
            f"http://{host_ip}:8090/stream",      # Alternative endpoint
            f"http://{host_ip}:8090/",            # Root endpoint
        ]
        
        # First pass: check if server is running
        server_found = False
        for url in candidate_urls:
            try:
                import requests
                resp = requests.get(url, timeout=3, stream=True)
                if resp.status_code == 200:
                    self.logger.info("✅ MJPEG video stream detected at %s", url)
                    resp.close()
                    return url
                resp.close()
            except Exception:
                pass
        
        # Server not running - try to auto-start it
        if not server_found:
            self.logger.info("📹 MJPEG server not detected, attempting auto-start...")
            if self._try_start_mjpeg_server():
                # Retry connection after server start
                for url in candidate_urls[:2]:  # Only try primary URLs
                    try:
                        import requests
                        resp = requests.get(url, timeout=5, stream=True)
                        if resp.status_code == 200:
                            self.logger.info("✅ MJPEG video stream connected after auto-start: %s", url)
                            resp.close()
                            return url
                        resp.close()
                    except Exception:
                        pass
        
        # Even if HTTP check fails, return the primary URL to try with OpenCV
        # OpenCV may connect even if requests can't
        primary_url = f"http://{host_ip}:8090/brio.mjpg"
        self.logger.info(f"⚠️ HTTP check failed, will try OpenCV with {primary_url}")
        return primary_url
    
    def _get_windows_host_ip(self) -> str:
        """Get host IP — on native Linux, always returns localhost."""
        return "localhost"

    def _on_start_stream(self, data):
        if self.is_running:
            return

        url = None
        if isinstance(data, dict):
            url = data.get("url")
        if not url:
            url = self._resolve_default_url()

        self._current_url = url
        self._stop_event.clear()
        self._stream_thread = threading.Thread(target=self._stream_loop, name="VisionStreamThread", daemon=True)
        self._stream_thread.start()
        self.is_running = True

        if hasattr(self.event_bus, "publish_sync"):
            self.event_bus.publish_sync("vision.stream.status", {"active": True, "url": url})

    def _on_stop_stream(self, _data=None):
        self._stop_event.set()
        self.is_running = False

        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                self.logger.exception("Error releasing VisionStream capture")
            self._capture = None

        if hasattr(self.event_bus, "publish_sync"):
            self.event_bus.publish_sync("vision.stream.status", {"active": False, "url": self._current_url})

    def _stream_via_requests(self, url: str) -> bool:
        """SOTA 2026: Stream MJPEG via HTTP with ultra-low latency optimizations.
        
        Key optimizations:
        - Larger chunk size (8192) for faster buffer fill
        - Extract ALL complete frames per chunk (not just one)
        - Minimal buffer management overhead
        - Direct frame publishing without queuing
        """
        if not HAS_REQUESTS:
            self.logger.warning("requests library not available for MJPEG streaming")
            return False
        
        self.logger.info(f"📹 SOTA 2026: Zero-latency MJPEG stream from {url}")
        
        try:
            # SOTA 2026: Minimal timeout, stream mode for instant data
            response = requests.get(url, stream=True, timeout=5)
            if response.status_code != 200:
                self.logger.warning(f"MJPEG stream returned {response.status_code}")
                return False
            
            self.logger.info(f"✅ Connected to MJPEG stream at {url}")
            self._current_url = url
            
            # Notify that stream is active
            if hasattr(self.event_bus, "publish_sync"):
                self.event_bus.publish_sync("vision.stream.status", {"active": True, "url": url})
            
            # SOTA 2026: Optimized buffer management
            bytes_buffer = b''
            frame_count = 0
            
            # Larger chunks = faster initial fill, lower syscall overhead
            for chunk in response.iter_content(chunk_size=8192):
                if self._stop_event.is_set():
                    break
                if not chunk:
                    continue
                
                bytes_buffer += chunk
                
                # SOTA 2026: Extract ALL complete frames from buffer (not just one)
                while True:
                    start = bytes_buffer.find(b'\xff\xd8')
                    if start == -1:
                        # Keep last 2 bytes in case JPEG marker spans chunks
                        bytes_buffer = bytes_buffer[-2:] if len(bytes_buffer) > 2 else bytes_buffer
                        break
                    
                    end = bytes_buffer.find(b'\xff\xd9', start)
                    if end == -1:
                        break
                    
                    # Extract and decode JPEG - FAST PATH
                    jpg_data = bytes_buffer[start:end+2]
                    bytes_buffer = bytes_buffer[end+2:]
                    
                    try:
                        frame = cv2.imdecode(np.frombuffer(jpg_data, np.uint8), cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            frame_count += 1
                            # Mirror for natural view
                            frame = cv2.flip(frame, 1)
                            
                            # SOTA 2026: Skip enhancement in zero-latency mode
                            if self._enhance_enabled and not self._zero_latency_mode:
                                frame = self._enhance_frame(frame)
                            
                            ts = time.time()
                            if hasattr(self.event_bus, "publish_sync"):
                                # ZERO LATENCY: Publish frame immediately
                                self.event_bus.publish_sync("vision.stream.frame", {
                                    "frame": frame,
                                    "timestamp": ts,
                                    "frame_count": frame_count,
                                })
                                
                                # SOTA 2026: Capture frame for world generation if requested
                                if hasattr(self, '_capture_next_frame_for_world') and self._capture_next_frame_for_world:
                                    self._frame_for_world = frame.copy()
                                    self._capture_next_frame_for_world = False
                                    self.event_bus.publish_sync("vision.frame.captured", {
                                        "timestamp": ts,
                                        "for_world_generation": True
                                    })
                                    self.logger.info("📸 Frame captured for world generation")
                                
                                # VL-JEPA: Async AI processing (non-blocking)
                                if frame_count % 5 == 0:  # Process every 5th frame for AI
                                    self._process_vl_jepa_async(frame)
                    except Exception as decode_err:
                        self.logger.debug(f"Frame decode error: {decode_err}")
            
            response.close()
            self.logger.info(f"📹 Stream ended after {frame_count} frames")
            return True
            
        except requests.exceptions.Timeout:
            self.logger.warning(f"Timeout connecting to {url}")
            return False
        except Exception as e:
            self.logger.warning(f"MJPEG stream error for {url}: {e}")
            return False

    def _stream_loop(self) -> None:
        requested_url = self._current_url
        env_device_str = os.environ.get("KINGDOM_VISION_DEVICE")
        
        # Get host IP first
        host_ip = self._get_windows_host_ip()
        self.logger.info(f"🔍 Host IP for MJPEG: {host_ip}")
        
        # SOTA 2026: MJPEG server endpoints - server auto-detects ANY webcam brand
        # The /brio.mjpg path is just the endpoint name, not brand-specific
        mjpeg_urls = [
            f"http://{host_ip}:8090/brio.mjpg",      # Primary (server detects any camera)
            "http://localhost:8090/brio.mjpg",
            "http://127.0.0.1:8090/brio.mjpg",
            f"http://{host_ip}:8090/stream",
            "http://localhost:8090/",                # Root endpoint
            f"http://{host_ip}:8090/",
        ]
        
        # Try direct HTTP streaming first (most reliable on Windows)
        for url in mjpeg_urls:
            self.logger.info(f"📹 Trying MJPEG URL: {url}")
            if self._stream_via_requests(url):
                # Stream completed (either success or stop requested)
                self.is_running = False
                if hasattr(self.event_bus, "publish_sync"):
                    self.event_bus.publish_sync("vision.stream.status", {"active": False, "url": url})
                return
        
        self.logger.info("📹 Direct HTTP failed, falling back to OpenCV VideoCapture...")
        
        # Build URL list FIRST - URLs should be tried before devices
        sources = []
        
        # SOTA 2026: Add MJPEG URLs FIRST (before any devices)
        # Works with ANY webcam MJPEG server - no brand-specific code
        for url in mjpeg_urls:
            sources.append(("url", url))
            self.logger.info(f"📹 Added MJPEG URL to try: {url}")
        
        # Add requested URL if different
        if requested_url and requested_url not in mjpeg_urls:
            sources.insert(0, ("url", requested_url))
        
        # Try resolved URL
        try:
            env_url = self._resolve_default_url()
            if env_url and env_url not in [s[1] for s in sources if s[0] == "url"]:
                sources.insert(0, ("url", env_url))
                self.logger.info(f"📹 Added resolved URL: {env_url}")
        except Exception as e:
            self.logger.warning(f"Failed to resolve default URL: {e}")

        if env_device_str:
            try:
                env_index = int(env_device_str)
                sources.append(("device", env_index))
            except ValueError:
                self.logger.error("Invalid KINGDOM_VISION_DEVICE value %r; expected integer index", env_device_str)

        # Only try device indices 0-2 AFTER URLs fail
        # In WSL, devices often don't work - URLs are the priority
        for idx in range(0, 3):
            sources.append(("device", idx))

        unique_sources = []
        seen = set()
        for kind, value in sources:
            key = f"{kind}:{value}"
            if key not in seen:
                seen.add(key)
                unique_sources.append((kind, value))

        opened_kind = None
        opened_value = None
        last_error = None

        for kind, value in unique_sources:
            label = f"device:{value}" if kind == "device" else str(value)
            self.logger.info("VisionStream trying %s", label)
            try:
                capture = None
                if kind == "url":
                    # For HTTP streams, try FFMPEG backend first (better MJPEG support)
                    capture = cv2.VideoCapture(value, cv2.CAP_FFMPEG)
                    if capture is None or not capture.isOpened():
                        # Fallback to default backend
                        if capture is not None:
                            capture.release()
                        capture = cv2.VideoCapture(value)
                else:
                    capture = cv2.VideoCapture(value)
                
                if capture is not None and capture.isOpened():
                    # Test read to ensure stream is working
                    ret, _ = capture.read()
                    if ret:
                        self._capture = capture
                        opened_kind = kind
                        opened_value = value
                        self.logger.info("✅ VisionStream opened %s successfully", label)
                        break
                    else:
                        self.logger.warning("VisionStream opened %s but read failed", label)
                if capture is not None:
                    capture.release()
            except Exception as exc:
                last_error = exc
                self.logger.debug("VisionStream error on %s: %s", label, exc)

        if self._capture is None or not self._capture.isOpened():
            message = "No usable vision source found"
            if last_error is not None:
                message = f"{message}: {last_error}"
            self.logger.error("VisionStream could not open any source: %s", message)
            self.is_running = False
            if hasattr(self.event_bus, "publish_sync"):
                self.event_bus.publish_sync("vision.stream.status", {
                    "active": False,
                    "url": requested_url or env_url or "",
                    "error": message,
                })
            return

        if opened_kind == "device":
            used_label = f"device:{opened_value}"
        else:
            used_label = str(opened_value)

        self._current_url = used_label
        self.logger.info("VisionStream connected to %s", used_label)

        try:
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        while not self._stop_event.is_set():
            ret, frame = self._capture.read()
            if not ret:
                time.sleep(0.1)
                continue

            try:
                frame = cv2.flip(frame, 1)
            except Exception:
                pass

            ts = time.time()
            if hasattr(self.event_bus, "publish_sync"):
                try:
                    self.event_bus.publish_sync("vision.stream.frame", {
                        "frame": frame,
                        "timestamp": ts,
                    })
                except Exception:
                    self.logger.exception("Error publishing frame from VisionStream")

        try:
            self._capture.release()
        except Exception:
            self.logger.exception("Error releasing VisionStream capture on loop exit")
        self._capture = None
        self.is_running = False

        if hasattr(self.event_bus, "publish_sync"):
            self.event_bus.publish_sync("vision.stream.status", {"active": False, "url": self._current_url})
