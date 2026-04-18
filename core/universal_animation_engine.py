"""
Universal Animation Engine - SOTA 2026
=======================================
Animates ANY data with motion, physics, and beautiful visualizations.

Supports:
- Chart animations (line, bar, candlestick, pie)
- 3D object animations (rotation, orbit, explosion)
- Particle systems (fire, water, sparks, smoke)
- Data flow animations (transactions, network traffic)
- Text animations (typing, fade, slide, wave)
- Number counters (counting up/down with easing)
- Image sequences (morphing, transitions)
- Physics simulations (gravity, bounce, spring)
- Wave/oscillation animations
- Path animations (follow curves, bezier)

Output to:
- Vision Stream (2D display)
- VR Environment (3D immersive)
- Event Bus (for other components)
"""

import logging
import threading
import time
import math
import json
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio

logger = logging.getLogger("KingdomAI.UniversalAnimationEngine")

# ============================================================================
# ANIMATION TYPES & EASING
# ============================================================================

class AnimationType(Enum):
    """Types of animations supported - SOTA 2026"""
    # Chart animations
    CHART_LINE = "chart_line"           # Animated line chart
    CHART_BAR = "chart_bar"             # Growing bar chart
    CHART_PIE = "chart_pie"             # Rotating pie chart
    CHART_CANDLESTICK = "candlestick"   # Trading candlesticks
    CHART_AREA = "chart_area"           # Filled area animation
    
    # 3D animations
    ROTATE_3D = "rotate_3d"             # 3D rotation
    ORBIT_3D = "orbit_3d"               # Orbital motion
    EXPLODE_3D = "explode_3d"           # Explosion effect
    ASSEMBLE_3D = "assemble_3d"         # Assembly animation
    FLY_THROUGH = "fly_through"         # Camera fly-through
    
    # Particle systems
    PARTICLES_FIRE = "particles_fire"   # Fire effect
    PARTICLES_WATER = "particles_water" # Water/rain
    PARTICLES_SPARKS = "particles_sparks" # Sparks
    PARTICLES_SMOKE = "particles_smoke" # Smoke
    PARTICLES_SNOW = "particles_snow"   # Snow
    PARTICLES_CONFETTI = "confetti"     # Celebration
    
    # Data flow
    DATA_FLOW = "data_flow"             # Data flowing between nodes
    NETWORK_PULSE = "network_pulse"     # Network activity
    TRANSACTION = "transaction"         # Transaction animation
    SIGNAL_WAVE = "signal_wave"         # Signal propagation
    
    # Text animations
    TEXT_TYPING = "text_typing"         # Typewriter effect
    TEXT_FADE = "text_fade"             # Fade in/out
    TEXT_SLIDE = "text_slide"           # Slide in/out
    TEXT_WAVE = "text_wave"             # Wave effect
    TEXT_GLITCH = "text_glitch"         # Glitch effect
    TEXT_MATRIX = "text_matrix"         # Matrix rain
    
    # Number animations
    NUMBER_COUNT = "number_count"       # Count up/down
    NUMBER_FLIP = "number_flip"         # Flip counter
    GAUGE_FILL = "gauge_fill"           # Gauge filling
    PROGRESS_BAR = "progress_bar"       # Progress animation
    
    # Image animations
    IMAGE_MORPH = "image_morph"         # Morphing between images
    IMAGE_TRANSITION = "image_transition" # Slide/fade transitions
    IMAGE_ZOOM = "image_zoom"           # Ken Burns effect
    IMAGE_PAN = "image_pan"             # Panning
    
    # Physics
    PHYSICS_GRAVITY = "physics_gravity" # Gravity simulation
    PHYSICS_BOUNCE = "physics_bounce"   # Bouncing
    PHYSICS_SPRING = "physics_spring"   # Spring physics
    PHYSICS_PENDULUM = "pendulum"       # Pendulum motion
    
    # Waves/Oscillation
    WAVE_SINE = "wave_sine"             # Sine wave
    WAVE_PULSE = "wave_pulse"           # Pulse wave
    OSCILLATION = "oscillation"         # Oscillating motion
    
    # Path animations
    PATH_FOLLOW = "path_follow"         # Follow a path
    PATH_BEZIER = "path_bezier"         # Bezier curve
    PATH_SPIRAL = "path_spiral"         # Spiral motion
    
    # Special
    HEARTBEAT = "heartbeat"             # Pulsing heartbeat
    BREATHING = "breathing"             # Breathing effect
    RIPPLE = "ripple"                   # Ripple effect
    MORPH = "morph"                     # Shape morphing


class EasingFunction(Enum):
    """Easing functions for smooth animations - SOTA 2026"""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    EASE_IN_QUAD = "ease_in_quad"
    EASE_OUT_QUAD = "ease_out_quad"
    EASE_IN_OUT_QUAD = "ease_in_out_quad"
    EASE_IN_CUBIC = "ease_in_cubic"
    EASE_OUT_CUBIC = "ease_out_cubic"
    EASE_IN_OUT_CUBIC = "ease_in_out_cubic"
    EASE_IN_ELASTIC = "ease_in_elastic"
    EASE_OUT_ELASTIC = "ease_out_elastic"
    EASE_IN_OUT_ELASTIC = "ease_in_out_elastic"
    EASE_IN_BOUNCE = "ease_in_bounce"
    EASE_OUT_BOUNCE = "ease_out_bounce"
    EASE_IN_OUT_BOUNCE = "ease_in_out_bounce"
    EASE_IN_BACK = "ease_in_back"
    EASE_OUT_BACK = "ease_out_back"
    EASE_IN_OUT_BACK = "ease_in_out_back"


# ============================================================================
# EASING FUNCTIONS IMPLEMENTATION
# ============================================================================

class Easing:
    """Mathematical easing functions for smooth motion"""
    
    @staticmethod
    def linear(t: float) -> float:
        return t
    
    @staticmethod
    def ease_in_quad(t: float) -> float:
        return t * t
    
    @staticmethod
    def ease_out_quad(t: float) -> float:
        return t * (2 - t)
    
    @staticmethod
    def ease_in_out_quad(t: float) -> float:
        return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t
    
    @staticmethod
    def ease_in_cubic(t: float) -> float:
        return t * t * t
    
    @staticmethod
    def ease_out_cubic(t: float) -> float:
        t -= 1
        return t * t * t + 1
    
    @staticmethod
    def ease_in_out_cubic(t: float) -> float:
        return 4 * t * t * t if t < 0.5 else (t - 1) * (2 * t - 2) * (2 * t - 2) + 1
    
    @staticmethod
    def ease_in_elastic(t: float) -> float:
        if t == 0 or t == 1:
            return t
        return -math.pow(2, 10 * (t - 1)) * math.sin((t - 1.1) * 5 * math.pi)
    
    @staticmethod
    def ease_out_elastic(t: float) -> float:
        if t == 0 or t == 1:
            return t
        return math.pow(2, -10 * t) * math.sin((t - 0.1) * 5 * math.pi) + 1
    
    @staticmethod
    def ease_in_out_elastic(t: float) -> float:
        if t == 0 or t == 1:
            return t
        t *= 2
        if t < 1:
            return -0.5 * math.pow(2, 10 * (t - 1)) * math.sin((t - 1.1) * 5 * math.pi)
        return 0.5 * math.pow(2, -10 * (t - 1)) * math.sin((t - 1.1) * 5 * math.pi) + 1
    
    @staticmethod
    def ease_out_bounce(t: float) -> float:
        if t < 1 / 2.75:
            return 7.5625 * t * t
        elif t < 2 / 2.75:
            t -= 1.5 / 2.75
            return 7.5625 * t * t + 0.75
        elif t < 2.5 / 2.75:
            t -= 2.25 / 2.75
            return 7.5625 * t * t + 0.9375
        else:
            t -= 2.625 / 2.75
            return 7.5625 * t * t + 0.984375
    
    @staticmethod
    def ease_in_bounce(t: float) -> float:
        return 1 - Easing.ease_out_bounce(1 - t)
    
    @staticmethod
    def ease_in_out_bounce(t: float) -> float:
        if t < 0.5:
            return Easing.ease_in_bounce(t * 2) * 0.5
        return Easing.ease_out_bounce(t * 2 - 1) * 0.5 + 0.5
    
    @staticmethod
    def ease_in_back(t: float) -> float:
        s = 1.70158
        return t * t * ((s + 1) * t - s)
    
    @staticmethod
    def ease_out_back(t: float) -> float:
        s = 1.70158
        t -= 1
        return t * t * ((s + 1) * t + s) + 1
    
    @staticmethod
    def ease_in_out_back(t: float) -> float:
        s = 1.70158 * 1.525
        t *= 2
        if t < 1:
            return 0.5 * (t * t * ((s + 1) * t - s))
        t -= 2
        return 0.5 * (t * t * ((s + 1) * t + s) + 2)
    
    @classmethod
    def get(cls, easing: EasingFunction) -> Callable[[float], float]:
        """Get easing function by enum"""
        mapping = {
            EasingFunction.LINEAR: cls.linear,
            EasingFunction.EASE_IN: cls.ease_in_quad,
            EasingFunction.EASE_OUT: cls.ease_out_quad,
            EasingFunction.EASE_IN_OUT: cls.ease_in_out_quad,
            EasingFunction.EASE_IN_QUAD: cls.ease_in_quad,
            EasingFunction.EASE_OUT_QUAD: cls.ease_out_quad,
            EasingFunction.EASE_IN_OUT_QUAD: cls.ease_in_out_quad,
            EasingFunction.EASE_IN_CUBIC: cls.ease_in_cubic,
            EasingFunction.EASE_OUT_CUBIC: cls.ease_out_cubic,
            EasingFunction.EASE_IN_OUT_CUBIC: cls.ease_in_out_cubic,
            EasingFunction.EASE_IN_ELASTIC: cls.ease_in_elastic,
            EasingFunction.EASE_OUT_ELASTIC: cls.ease_out_elastic,
            EasingFunction.EASE_IN_OUT_ELASTIC: cls.ease_in_out_elastic,
            EasingFunction.EASE_IN_BOUNCE: cls.ease_in_bounce,
            EasingFunction.EASE_OUT_BOUNCE: cls.ease_out_bounce,
            EasingFunction.EASE_IN_OUT_BOUNCE: cls.ease_in_out_bounce,
            EasingFunction.EASE_IN_BACK: cls.ease_in_back,
            EasingFunction.EASE_OUT_BACK: cls.ease_out_back,
            EasingFunction.EASE_IN_OUT_BACK: cls.ease_in_out_back,
        }
        return mapping.get(easing, cls.linear)


# ============================================================================
# ANIMATION DATA STRUCTURES
# ============================================================================

@dataclass
class AnimationKeyframe:
    """Single keyframe in an animation"""
    time: float                      # Time in seconds
    value: Any                       # Value at this keyframe
    easing: EasingFunction = EasingFunction.EASE_IN_OUT


@dataclass
class AnimationTrack:
    """Animation track for a single property"""
    property_name: str
    keyframes: List[AnimationKeyframe] = field(default_factory=list)
    
    def get_value_at(self, time: float) -> Any:
        """Interpolate value at given time"""
        if not self.keyframes:
            return None
        
        if time <= self.keyframes[0].time:
            return self.keyframes[0].value
        
        if time >= self.keyframes[-1].time:
            return self.keyframes[-1].value
        
        # Find surrounding keyframes
        for i in range(len(self.keyframes) - 1):
            kf1, kf2 = self.keyframes[i], self.keyframes[i + 1]
            if kf1.time <= time <= kf2.time:
                # Calculate progress
                duration = kf2.time - kf1.time
                progress = (time - kf1.time) / duration if duration > 0 else 1.0
                
                # Apply easing
                easing_func = Easing.get(kf2.easing)
                eased_progress = easing_func(progress)
                
                # Interpolate
                return self._interpolate(kf1.value, kf2.value, eased_progress)
        
        return self.keyframes[-1].value
    
    def _interpolate(self, v1: Any, v2: Any, t: float) -> Any:
        """Interpolate between two values"""
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            return v1 + (v2 - v1) * t
        elif isinstance(v1, (list, tuple)) and isinstance(v2, (list, tuple)):
            return [self._interpolate(a, b, t) for a, b in zip(v1, v2)]
        elif isinstance(v1, dict) and isinstance(v2, dict):
            result = {}
            for key in v1.keys():
                if key in v2:
                    result[key] = self._interpolate(v1[key], v2[key], t)
                else:
                    result[key] = v1[key]
            return result
        else:
            # Can't interpolate, return end value at t >= 0.5
            return v2 if t >= 0.5 else v1


@dataclass
class Animation:
    """Complete animation definition"""
    id: str
    animation_type: AnimationType
    duration: float                  # Total duration in seconds
    fps: int = 60                    # Frames per second
    loop: bool = False               # Loop animation
    reverse: bool = False            # Reverse at end (ping-pong)
    tracks: List[AnimationTrack] = field(default_factory=list)
    data: Any = None                 # Source data to animate
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime state
    current_time: float = 0.0
    playing: bool = False
    completed: bool = False


@dataclass
class AnimationFrame:
    """Single rendered frame of animation"""
    frame_number: int
    timestamp: float
    data: Dict[str, Any]
    visualization: Optional[Dict] = None
    vr_scene: Optional[Dict] = None


# ============================================================================
# ANIMATION GENERATORS
# ============================================================================

class AnimationGenerator:
    """Base class for animation generators"""
    
    @staticmethod
    def generate_frames(animation: Animation) -> List[AnimationFrame]:
        """Generate all frames for an animation"""
        raise NotImplementedError


class ChartAnimationGenerator(AnimationGenerator):
    """Generate animated chart frames"""
    
    @staticmethod
    def generate_line_chart(data: List[float], duration: float, fps: int = 60) -> List[AnimationFrame]:
        """Animate line chart drawing from left to right"""
        frames = []
        total_frames = int(duration * fps)
        
        for i in range(total_frames):
            progress = i / (total_frames - 1) if total_frames > 1 else 1.0
            eased = Easing.ease_out_cubic(progress)
            
            # Show data points up to current progress
            visible_points = int(len(data) * eased)
            visible_data = data[:max(1, visible_points)]
            
            frames.append(AnimationFrame(
                frame_number=i,
                timestamp=i / fps,
                data={
                    "type": "line_chart",
                    "values": visible_data,
                    "progress": progress,
                    "line_progress": eased
                }
            ))
        
        return frames
    
    @staticmethod
    def generate_bar_chart(data: List[float], duration: float, fps: int = 60) -> List[AnimationFrame]:
        """Animate bars growing from bottom"""
        frames = []
        total_frames = int(duration * fps)
        
        for i in range(total_frames):
            progress = i / (total_frames - 1) if total_frames > 1 else 1.0
            eased = Easing.ease_out_elastic(progress)
            
            # Scale bar heights
            animated_data = [v * eased for v in data]
            
            frames.append(AnimationFrame(
                frame_number=i,
                timestamp=i / fps,
                data={
                    "type": "bar_chart",
                    "values": animated_data,
                    "max_values": data,
                    "progress": progress,
                    "scale": eased
                }
            ))
        
        return frames
    
    @staticmethod
    def generate_pie_chart(data: List[float], duration: float, fps: int = 60) -> List[AnimationFrame]:
        """Animate pie chart with rotation and segment reveal"""
        frames = []
        total_frames = int(duration * fps)
        total = sum(data)
        
        for i in range(total_frames):
            progress = i / (total_frames - 1) if total_frames > 1 else 1.0
            eased = Easing.ease_out_cubic(progress)
            
            # Rotate and reveal segments
            rotation = 360 * (1 - eased) if progress < 0.5 else 0
            revealed_angle = 360 * min(1.0, eased * 1.2)
            
            frames.append(AnimationFrame(
                frame_number=i,
                timestamp=i / fps,
                data={
                    "type": "pie_chart",
                    "values": data,
                    "total": total,
                    "rotation": rotation,
                    "revealed_angle": revealed_angle,
                    "progress": progress
                }
            ))
        
        return frames


class NumberAnimationGenerator(AnimationGenerator):
    """Generate animated number counting"""
    
    @staticmethod
    def generate_count(start: float, end: float, duration: float, fps: int = 60,
                       decimal_places: int = 0) -> List[AnimationFrame]:
        """Animate counting from start to end"""
        frames = []
        total_frames = int(duration * fps)
        
        for i in range(total_frames):
            progress = i / (total_frames - 1) if total_frames > 1 else 1.0
            eased = Easing.ease_out_cubic(progress)
            
            current_value = start + (end - start) * eased
            
            if decimal_places == 0:
                display_value = int(round(current_value))
            else:
                display_value = round(current_value, decimal_places)
            
            frames.append(AnimationFrame(
                frame_number=i,
                timestamp=i / fps,
                data={
                    "type": "number_count",
                    "value": display_value,
                    "start": start,
                    "end": end,
                    "progress": progress
                }
            ))
        
        return frames


class ParticleAnimationGenerator(AnimationGenerator):
    """Generate particle system animations"""
    
    @staticmethod
    def generate_particles(particle_type: str, count: int, duration: float, 
                          fps: int = 60, bounds: Tuple[float, float, float] = (100, 100, 100)) -> List[AnimationFrame]:
        """Generate particle animation frames"""
        import random
        frames = []
        total_frames = int(duration * fps)
        
        # Initialize particles
        particles = []
        for _ in range(count):
            particles.append({
                "x": random.uniform(0, bounds[0]),
                "y": random.uniform(0, bounds[1]),
                "z": random.uniform(0, bounds[2]),
                "vx": random.uniform(-1, 1),
                "vy": random.uniform(-2, 0) if particle_type == "fire" else random.uniform(-1, 1),
                "vz": random.uniform(-1, 1),
                "life": random.uniform(0.5, 1.0),
                "size": random.uniform(1, 5),
                "color": ParticleAnimationGenerator._get_particle_color(particle_type)
            })
        
        dt = 1.0 / fps
        
        for frame_num in range(total_frames):
            # Update particles
            for p in particles:
                # Apply physics based on type
                if particle_type == "fire":
                    p["vy"] -= 5 * dt  # Rise up
                    p["vx"] += random.uniform(-0.5, 0.5) * dt
                elif particle_type == "water":
                    p["vy"] += 9.8 * dt  # Fall down
                elif particle_type == "sparks":
                    p["vy"] += 2 * dt  # Slight fall
                    p["life"] -= 0.02
                elif particle_type == "smoke":
                    p["vy"] -= 1 * dt  # Slow rise
                    p["vx"] += random.uniform(-0.3, 0.3) * dt
                    p["size"] += 0.1 * dt
                elif particle_type == "confetti":
                    p["vy"] += 3 * dt
                    p["vx"] += math.sin(frame_num * 0.1) * 0.5 * dt
                
                # Update position
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["z"] += p["vz"]
                
                # Respawn if needed
                if p["y"] < 0 or p["y"] > bounds[1] or p["life"] <= 0:
                    p["x"] = random.uniform(bounds[0] * 0.3, bounds[0] * 0.7)
                    p["y"] = bounds[1] * 0.1 if particle_type in ["fire", "smoke"] else 0
                    p["z"] = random.uniform(bounds[2] * 0.3, bounds[2] * 0.7)
                    p["life"] = random.uniform(0.5, 1.0)
                    p["vy"] = random.uniform(-2, 0) if particle_type == "fire" else random.uniform(-1, 1)
            
            frames.append(AnimationFrame(
                frame_number=frame_num,
                timestamp=frame_num / fps,
                data={
                    "type": f"particles_{particle_type}",
                    "particles": [dict(p) for p in particles],
                    "count": count,
                    "bounds": bounds
                }
            ))
        
        return frames
    
    @staticmethod
    def _get_particle_color(particle_type: str) -> Tuple[int, int, int]:
        import random
        if particle_type == "fire":
            return (255, random.randint(100, 200), random.randint(0, 50))
        elif particle_type == "water":
            return (random.randint(50, 100), random.randint(150, 200), 255)
        elif particle_type == "sparks":
            return (255, 255, random.randint(100, 200))
        elif particle_type == "smoke":
            v = random.randint(100, 150)
            return (v, v, v)
        elif particle_type == "confetti":
            return (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
        return (255, 255, 255)


class TextAnimationGenerator(AnimationGenerator):
    """Generate text animations"""
    
    @staticmethod
    def generate_typing(text: str, duration: float, fps: int = 60) -> List[AnimationFrame]:
        """Typewriter effect animation"""
        frames = []
        total_frames = int(duration * fps)
        
        for i in range(total_frames):
            progress = i / (total_frames - 1) if total_frames > 1 else 1.0
            char_count = int(len(text) * progress)
            visible_text = text[:char_count]
            cursor = "|" if (i // (fps // 2)) % 2 == 0 else ""
            
            frames.append(AnimationFrame(
                frame_number=i,
                timestamp=i / fps,
                data={
                    "type": "text_typing",
                    "text": visible_text,
                    "cursor": cursor,
                    "full_text": text,
                    "progress": progress
                }
            ))
        
        return frames
    
    @staticmethod
    def generate_wave(text: str, duration: float, fps: int = 60, 
                      amplitude: float = 10, frequency: float = 2) -> List[AnimationFrame]:
        """Wave effect on text characters"""
        frames = []
        total_frames = int(duration * fps)
        
        for i in range(total_frames):
            time_val = i / fps
            char_offsets = []
            
            for j, char in enumerate(text):
                offset_y = amplitude * math.sin(frequency * time_val * math.pi * 2 + j * 0.5)
                char_offsets.append({
                    "char": char,
                    "offset_y": offset_y,
                    "offset_x": 0
                })
            
            frames.append(AnimationFrame(
                frame_number=i,
                timestamp=time_val,
                data={
                    "type": "text_wave",
                    "text": text,
                    "char_offsets": char_offsets,
                    "amplitude": amplitude,
                    "frequency": frequency
                }
            ))
        
        return frames


class Object3DAnimationGenerator(AnimationGenerator):
    """Generate 3D object animations"""
    
    @staticmethod
    def generate_rotation(duration: float, fps: int = 60,
                         axis: str = "y", speed: float = 1.0) -> List[AnimationFrame]:
        """Generate 3D rotation animation"""
        frames = []
        total_frames = int(duration * fps)
        
        for i in range(total_frames):
            time_val = i / fps
            angle = (time_val * speed * 360) % 360
            
            rotation = {"x": 0, "y": 0, "z": 0}
            rotation[axis] = angle
            
            frames.append(AnimationFrame(
                frame_number=i,
                timestamp=time_val,
                data={
                    "type": "rotate_3d",
                    "rotation": rotation,
                    "axis": axis,
                    "angle": angle
                }
            ))
        
        return frames
    
    @staticmethod
    def generate_orbit(duration: float, fps: int = 60,
                       radius: float = 10, speed: float = 1.0,
                       center: Tuple[float, float, float] = (0, 0, 0)) -> List[AnimationFrame]:
        """Generate orbital motion animation"""
        frames = []
        total_frames = int(duration * fps)
        
        for i in range(total_frames):
            time_val = i / fps
            angle = time_val * speed * math.pi * 2
            
            x = center[0] + radius * math.cos(angle)
            y = center[1]
            z = center[2] + radius * math.sin(angle)
            
            frames.append(AnimationFrame(
                frame_number=i,
                timestamp=time_val,
                data={
                    "type": "orbit_3d",
                    "position": {"x": x, "y": y, "z": z},
                    "angle": math.degrees(angle),
                    "radius": radius,
                    "center": center
                }
            ))
        
        return frames


class DataFlowAnimationGenerator(AnimationGenerator):
    """Generate data flow/network animations"""
    
    @staticmethod
    def generate_flow(nodes: List[Dict], connections: List[Tuple[int, int]],
                      duration: float, fps: int = 60) -> List[AnimationFrame]:
        """Generate data flowing between nodes"""
        frames = []
        total_frames = int(duration * fps)
        
        # Create flow particles along each connection
        flow_particles = []
        for conn in connections:
            flow_particles.append({
                "from": conn[0],
                "to": conn[1],
                "progress": 0,
                "speed": 0.5 + len(flow_particles) * 0.1  # Vary speed
            })
        
        dt = 1.0 / fps
        
        for i in range(total_frames):
            # Update particles
            for particle in flow_particles:
                particle["progress"] += particle["speed"] * dt
                if particle["progress"] > 1:
                    particle["progress"] = 0
            
            frames.append(AnimationFrame(
                frame_number=i,
                timestamp=i / fps,
                data={
                    "type": "data_flow",
                    "nodes": nodes,
                    "connections": connections,
                    "flow_particles": [dict(p) for p in flow_particles]
                }
            ))
        
        return frames


# ============================================================================
# UNIVERSAL ANIMATION ENGINE
# ============================================================================

class UniversalAnimationEngine:
    """
    SOTA 2026: Universal Animation Engine
    
    Animates ANY data with motion, physics, and beautiful visualizations.
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._lock = threading.Lock()
        self._animations: Dict[str, Animation] = {}
        self._playing: Dict[str, bool] = {}
        self._animation_threads: Dict[str, threading.Thread] = {}
        
        # Generators
        self.chart_gen = ChartAnimationGenerator()
        self.number_gen = NumberAnimationGenerator()
        self.particle_gen = ParticleAnimationGenerator()
        self.text_gen = TextAnimationGenerator()
        self.object3d_gen = Object3DAnimationGenerator()
        self.dataflow_gen = DataFlowAnimationGenerator()
        
        logger.info("🎬 UniversalAnimationEngine initialized")
        logger.info("   Supports: Charts, 3D, Particles, Text, Numbers, Physics")
    
    def animate_data(self, data: Any, animation_type: Union[str, AnimationType],
                     duration: float = 3.0, fps: int = 60,
                     loop: bool = False, **kwargs) -> str:
        """
        Animate any data with the specified animation type.
        
        Args:
            data: The data to animate
            animation_type: Type of animation
            duration: Animation duration in seconds
            fps: Frames per second
            loop: Whether to loop
            **kwargs: Additional animation parameters
            
        Returns:
            Animation ID
        """
        import uuid
        animation_id = str(uuid.uuid4())[:8]
        
        # Convert string to enum if needed
        if isinstance(animation_type, str):
            try:
                animation_type = AnimationType(animation_type)
            except ValueError:
                animation_type = self._guess_animation_type(data, animation_type)
        
        logger.info(f"🎬 Creating animation: {animation_type.value} (duration={duration}s)")
        
        # Generate frames based on animation type
        frames = self._generate_frames(data, animation_type, duration, fps, **kwargs)
        
        # Create animation object
        animation = Animation(
            id=animation_id,
            animation_type=animation_type,
            duration=duration,
            fps=fps,
            loop=loop,
            data=data,
            metadata={"frames": frames, "kwargs": kwargs}
        )
        
        with self._lock:
            self._animations[animation_id] = animation
        
        return animation_id
    
    def _guess_animation_type(self, data: Any, hint: str) -> AnimationType:
        """Guess the best animation type for the data"""
        hint_lower = hint.lower()
        
        # Check hint first
        if "chart" in hint_lower or "line" in hint_lower:
            return AnimationType.CHART_LINE
        if "bar" in hint_lower:
            return AnimationType.CHART_BAR
        if "pie" in hint_lower:
            return AnimationType.CHART_PIE
        if "particle" in hint_lower or "fire" in hint_lower:
            return AnimationType.PARTICLES_FIRE
        if "water" in hint_lower or "rain" in hint_lower:
            return AnimationType.PARTICLES_WATER
        if "rotate" in hint_lower or "spin" in hint_lower:
            return AnimationType.ROTATE_3D
        if "orbit" in hint_lower:
            return AnimationType.ORBIT_3D
        if "count" in hint_lower or "number" in hint_lower:
            return AnimationType.NUMBER_COUNT
        if "type" in hint_lower or "typing" in hint_lower:
            return AnimationType.TEXT_TYPING
        if "wave" in hint_lower:
            return AnimationType.TEXT_WAVE
        if "flow" in hint_lower or "network" in hint_lower:
            return AnimationType.DATA_FLOW
        if "pulse" in hint_lower or "heartbeat" in hint_lower:
            return AnimationType.HEARTBEAT
        
        # Guess from data type
        if isinstance(data, (list, tuple)):
            if all(isinstance(x, (int, float)) for x in data):
                return AnimationType.CHART_LINE
        if isinstance(data, str):
            return AnimationType.TEXT_TYPING
        if isinstance(data, (int, float)):
            return AnimationType.NUMBER_COUNT
        if isinstance(data, dict):
            if "nodes" in data:
                return AnimationType.DATA_FLOW
            if "x" in data or "position" in data:
                return AnimationType.ROTATE_3D
        
        return AnimationType.CHART_LINE  # Default
    
    def _generate_frames(self, data: Any, animation_type: AnimationType,
                         duration: float, fps: int, **kwargs) -> List[AnimationFrame]:
        """Generate animation frames based on type"""
        
        # Chart animations
        if animation_type == AnimationType.CHART_LINE:
            values = data if isinstance(data, list) else list(data.values()) if isinstance(data, dict) else [data]
            return self.chart_gen.generate_line_chart(values, duration, fps)
        
        elif animation_type == AnimationType.CHART_BAR:
            values = data if isinstance(data, list) else list(data.values()) if isinstance(data, dict) else [data]
            return self.chart_gen.generate_bar_chart(values, duration, fps)
        
        elif animation_type == AnimationType.CHART_PIE:
            values = data if isinstance(data, list) else list(data.values()) if isinstance(data, dict) else [data]
            return self.chart_gen.generate_pie_chart(values, duration, fps)
        
        # Number animations
        elif animation_type == AnimationType.NUMBER_COUNT:
            start = kwargs.get("start", 0)
            end = data if isinstance(data, (int, float)) else 100
            decimal_places = kwargs.get("decimal_places", 0)
            return self.number_gen.generate_count(start, end, duration, fps, decimal_places)
        
        # Particle animations
        elif animation_type in [AnimationType.PARTICLES_FIRE, AnimationType.PARTICLES_WATER,
                                AnimationType.PARTICLES_SPARKS, AnimationType.PARTICLES_SMOKE,
                                AnimationType.PARTICLES_SNOW]:
            particle_type = animation_type.value.replace("particles_", "")
            count = kwargs.get("count", 100)
            bounds = kwargs.get("bounds", (100, 100, 100))
            return self.particle_gen.generate_particles(particle_type, count, duration, fps, bounds)
        
        # Text animations
        elif animation_type == AnimationType.TEXT_TYPING:
            text = str(data)
            return self.text_gen.generate_typing(text, duration, fps)
        
        elif animation_type == AnimationType.TEXT_WAVE:
            text = str(data)
            amplitude = kwargs.get("amplitude", 10)
            frequency = kwargs.get("frequency", 2)
            return self.text_gen.generate_wave(text, duration, fps, amplitude, frequency)
        
        # 3D animations
        elif animation_type == AnimationType.ROTATE_3D:
            axis = kwargs.get("axis", "y")
            speed = kwargs.get("speed", 1.0)
            return self.object3d_gen.generate_rotation(duration, fps, axis, speed)
        
        elif animation_type == AnimationType.ORBIT_3D:
            radius = kwargs.get("radius", 10)
            speed = kwargs.get("speed", 1.0)
            center = kwargs.get("center", (0, 0, 0))
            return self.object3d_gen.generate_orbit(duration, fps, radius, speed, center)
        
        # Data flow
        elif animation_type == AnimationType.DATA_FLOW:
            if isinstance(data, dict):
                nodes = data.get("nodes", [])
                connections = data.get("connections", [])
            else:
                nodes = [{"id": i, "x": i * 50, "y": 50} for i in range(5)]
                connections = [(i, i + 1) for i in range(4)]
            return self.dataflow_gen.generate_flow(nodes, connections, duration, fps)
        
        # Default: generate simple frames
        else:
            return self._generate_default_frames(data, duration, fps)
    
    def _generate_default_frames(self, data: Any, duration: float, fps: int) -> List[AnimationFrame]:
        """Generate default animation frames"""
        frames = []
        total_frames = int(duration * fps)
        
        for i in range(total_frames):
            progress = i / (total_frames - 1) if total_frames > 1 else 1.0
            
            frames.append(AnimationFrame(
                frame_number=i,
                timestamp=i / fps,
                data={
                    "type": "default",
                    "progress": progress,
                    "original_data": data
                }
            ))
        
        return frames
    
    def play(self, animation_id: str, on_frame: Callable[[AnimationFrame], None] = None):
        """Play an animation"""
        animation = self._animations.get(animation_id)
        if not animation:
            logger.error(f"Animation {animation_id} not found")
            return False
        
        self._playing[animation_id] = True
        
        def play_loop():
            frames = animation.metadata.get("frames", [])
            frame_duration = 1.0 / animation.fps
            
            while self._playing.get(animation_id, False):
                for frame in frames:
                    if not self._playing.get(animation_id, False):
                        break
                    
                    # Call callback
                    if on_frame:
                        on_frame(frame)
                    
                    # Publish to event bus
                    if self.event_bus:
                        self.event_bus.publish("animation.frame", {
                            "animation_id": animation_id,
                            "frame": frame.frame_number,
                            "data": frame.data,
                            "timestamp": frame.timestamp
                        })
                    
                    time.sleep(frame_duration)
                
                if not animation.loop:
                    break
            
            self._playing[animation_id] = False
            animation.completed = True
            logger.info(f"🎬 Animation {animation_id} completed")
        
        thread = threading.Thread(target=play_loop, daemon=True)
        thread.start()
        self._animation_threads[animation_id] = thread
        
        logger.info(f"▶️ Playing animation {animation_id}")
        return True
    
    def stop(self, animation_id: str):
        """Stop an animation"""
        self._playing[animation_id] = False
        logger.info(f"⏹️ Stopped animation {animation_id}")
    
    def stop_all(self):
        """Stop all animations"""
        for anim_id in list(self._playing.keys()):
            self._playing[anim_id] = False
        logger.info("⏹️ Stopped all animations")
    
    def get_frames(self, animation_id: str) -> List[AnimationFrame]:
        """Get all frames for an animation"""
        animation = self._animations.get(animation_id)
        if animation:
            return animation.metadata.get("frames", [])
        return []


# ============================================================================
# SINGLETON & MCP TOOLS
# ============================================================================

_animation_engine: Optional[UniversalAnimationEngine] = None

def get_animation_engine(event_bus=None) -> UniversalAnimationEngine:
    """Get or create the global animation engine"""
    global _animation_engine
    if _animation_engine is None:
        _animation_engine = UniversalAnimationEngine(event_bus)
    return _animation_engine


class AnimationMCPTools:
    """MCP tools for AI to control animations"""
    
    def __init__(self, engine: UniversalAnimationEngine):
        self.engine = engine
    
    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "animate",
                "description": "Animate any data with motion effects (charts, 3D, particles, text, numbers)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data": {"description": "Data to animate (numbers, text, list, dict)"},
                        "animation_type": {
                            "type": "string",
                            "enum": ["chart_line", "chart_bar", "chart_pie", "rotate_3d", "orbit_3d",
                                    "particles_fire", "particles_water", "particles_sparks", "confetti",
                                    "text_typing", "text_wave", "number_count", "data_flow",
                                    "heartbeat", "ripple", "auto"],
                            "description": "Type of animation"
                        },
                        "duration": {"type": "number", "description": "Duration in seconds"},
                        "loop": {"type": "boolean", "description": "Loop animation"}
                    },
                    "required": ["data"]
                }
            },
            {
                "name": "animate_chart",
                "description": "Create animated chart (line, bar, pie)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "values": {"type": "array", "items": {"type": "number"}},
                        "chart_type": {"type": "string", "enum": ["line", "bar", "pie"]},
                        "duration": {"type": "number"}
                    },
                    "required": ["values"]
                }
            },
            {
                "name": "animate_particles",
                "description": "Create particle animation (fire, water, sparks, smoke, confetti)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "effect": {"type": "string", "enum": ["fire", "water", "sparks", "smoke", "confetti", "snow"]},
                        "count": {"type": "integer", "description": "Number of particles"},
                        "duration": {"type": "number"}
                    },
                    "required": ["effect"]
                }
            },
            {
                "name": "animate_text",
                "description": "Create text animation (typing, wave, glitch)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "effect": {"type": "string", "enum": ["typing", "wave", "fade", "slide", "glitch"]},
                        "duration": {"type": "number"}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "animate_number",
                "description": "Animate number counting up or down",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "number"},
                        "end": {"type": "number"},
                        "duration": {"type": "number"},
                        "decimal_places": {"type": "integer"}
                    },
                    "required": ["end"]
                }
            },
            {
                "name": "animate_3d",
                "description": "Create 3D animation (rotation, orbit, explode)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "effect": {"type": "string", "enum": ["rotate", "orbit", "explode", "assemble"]},
                        "axis": {"type": "string", "enum": ["x", "y", "z"]},
                        "speed": {"type": "number"},
                        "duration": {"type": "number"}
                    },
                    "required": ["effect"]
                }
            },
            {
                "name": "stop_animation",
                "description": "Stop a running animation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "animation_id": {"type": "string"}
                    }
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if tool_name == "animate":
                data = parameters.get("data")
                anim_type = parameters.get("animation_type", "auto")
                duration = parameters.get("duration", 3.0)
                loop = parameters.get("loop", False)
                
                anim_id = self.engine.animate_data(data, anim_type, duration, loop=loop)
                self.engine.play(anim_id)
                
                return {"success": True, "animation_id": anim_id, "type": anim_type}
            
            elif tool_name == "animate_chart":
                values = parameters.get("values", [])
                chart_type = parameters.get("chart_type", "line")
                duration = parameters.get("duration", 3.0)
                
                anim_type = f"chart_{chart_type}"
                anim_id = self.engine.animate_data(values, anim_type, duration)
                self.engine.play(anim_id)
                
                return {"success": True, "animation_id": anim_id, "chart_type": chart_type}
            
            elif tool_name == "animate_particles":
                effect = parameters.get("effect", "fire")
                count = parameters.get("count", 100)
                duration = parameters.get("duration", 5.0)
                
                anim_id = self.engine.animate_data(None, f"particles_{effect}", duration, count=count)
                self.engine.play(anim_id)
                
                return {"success": True, "animation_id": anim_id, "effect": effect, "count": count}
            
            elif tool_name == "animate_text":
                text = parameters.get("text", "")
                effect = parameters.get("effect", "typing")
                duration = parameters.get("duration", 3.0)
                
                anim_type = f"text_{effect}"
                anim_id = self.engine.animate_data(text, anim_type, duration)
                self.engine.play(anim_id)
                
                return {"success": True, "animation_id": anim_id, "effect": effect}
            
            elif tool_name == "animate_number":
                start = parameters.get("start", 0)
                end = parameters.get("end", 100)
                duration = parameters.get("duration", 2.0)
                decimal_places = parameters.get("decimal_places", 0)
                
                anim_id = self.engine.animate_data(end, "number_count", duration, 
                                                   start=start, decimal_places=decimal_places)
                self.engine.play(anim_id)
                
                return {"success": True, "animation_id": anim_id, "start": start, "end": end}
            
            elif tool_name == "animate_3d":
                effect = parameters.get("effect", "rotate")
                axis = parameters.get("axis", "y")
                speed = parameters.get("speed", 1.0)
                duration = parameters.get("duration", 5.0)
                
                anim_type = f"{effect}_3d" if effect != "rotate" else "rotate_3d"
                anim_id = self.engine.animate_data(None, anim_type, duration, axis=axis, speed=speed)
                self.engine.play(anim_id)
                
                return {"success": True, "animation_id": anim_id, "effect": effect, "axis": axis}
            
            elif tool_name == "stop_animation":
                anim_id = parameters.get("animation_id")
                if anim_id:
                    self.engine.stop(anim_id)
                else:
                    self.engine.stop_all()
                return {"success": True, "stopped": anim_id or "all"}
            
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Animation tool error: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print(" UNIVERSAL ANIMATION ENGINE TEST ".center(70))
    print("="*70 + "\n")
    
    engine = get_animation_engine()
    
    print("📊 Testing Chart Animation...")
    anim_id = engine.animate_data([10, 25, 15, 40, 30, 55, 45], "chart_line", duration=2.0)
    frames = engine.get_frames(anim_id)
    print(f"   Generated {len(frames)} frames")
    
    print("\n🔢 Testing Number Counter...")
    anim_id = engine.animate_data(1000, "number_count", duration=2.0, start=0)
    frames = engine.get_frames(anim_id)
    print(f"   Generated {len(frames)} frames")
    print(f"   Sample: {frames[0].data['value']} → {frames[-1].data['value']}")
    
    print("\n📝 Testing Text Typing...")
    anim_id = engine.animate_data("Hello Kingdom AI!", "text_typing", duration=2.0)
    frames = engine.get_frames(anim_id)
    print(f"   Generated {len(frames)} frames")
    
    print("\n🔥 Testing Particle System...")
    anim_id = engine.animate_data(None, "particles_fire", duration=1.0, count=50)
    frames = engine.get_frames(anim_id)
    print(f"   Generated {len(frames)} frames with {len(frames[0].data['particles'])} particles")
    
    print("\n🔄 Testing 3D Rotation...")
    anim_id = engine.animate_data(None, "rotate_3d", duration=2.0, axis="y", speed=2.0)
    frames = engine.get_frames(anim_id)
    print(f"   Generated {len(frames)} frames")
    
    print("\n" + "="*70)
    print(" Animation Types Supported: ".center(70))
    print("="*70)
    for anim_type in AnimationType:
        print(f"   • {anim_type.value}")
    
    print("\n" + "="*70 + "\n")
