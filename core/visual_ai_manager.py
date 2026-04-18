#!/usr/bin/env python3
"""
Kingdom AI - SOTA 2026 Unified Visual AI Manager

Central coordinator for all visual AI systems including:
- Image generation and processing
- Animation creation and playback
- Technical visualization (math, charts, diagrams)
- Ollama vision integration
- Continuous learning from visual interactions
- Style memory and meta-learning
- Sentience-aware visual processing

This module provides a single interface for all visual AI operations
across the entire Kingdom AI system.
"""

import os
import sys
import asyncio
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from core.ai_visual_engine import AIVisualEngine, SOTAAnimationEngine, VisualMode, VisualConfig, VisualResult
    from core.ollama_learning_integration import OllamaLearningSystem
from dataclasses import dataclass, field
from pathlib import Path

# Configure logging
logger = logging.getLogger("KingdomAI.VisualAIManager")

# Import core visual systems
try:
    from core.ai_visual_engine import (
        AIVisualEngine, AIImageGenerator, OllamaVisionProcessor,
        SOTAAnimationEngine, VisualMode, VisualConfig, VisualResult,
        get_visual_engine
    )
    AI_VISUAL_ENGINE_AVAILABLE = True
except (ImportError, RuntimeError, Exception) as e:
    logger.warning(f"AI Visual Engine not available: {e}")
    AI_VISUAL_ENGINE_AVAILABLE = False
    AIVisualEngine = None
    AIImageGenerator = None
    OllamaVisionProcessor = None
    SOTAAnimationEngine = None
    VisualMode = None
    VisualConfig = None
    VisualResult = None
    get_visual_engine = None

try:
    from core.ollama_learning_integration import (
        OllamaLearningSystem, OllamaModelRouter, TaskType,
        get_learning_system
    )
    OLLAMA_LEARNING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Ollama Learning System not available: {e}")
    OLLAMA_LEARNING_AVAILABLE = False

try:
    from gui.widgets.technical_visualization_engine import (
        TechnicalVisualizationEngine, TechnicalMode, TechnicalConfig
    )
    TECHNICAL_VIZ_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Technical Visualization Engine not available: {e}")
    TECHNICAL_VIZ_AVAILABLE = False


@dataclass
class VisualAIStatus:
    """Status of the Visual AI Manager."""
    initialized: bool = False
    visual_engine_active: bool = False
    learning_system_active: bool = False
    technical_viz_active: bool = False
    ollama_connected: bool = False
    available_models: List[str] = field(default_factory=list)
    backends: Dict[str, bool] = field(default_factory=dict)
    stats: Dict[str, int] = field(default_factory=dict)


class VisualAIManager:
    """
    SOTA 2026 Unified Visual AI Manager
    
    Coordinates all visual AI systems and provides a unified interface
    for image generation, analysis, animation, and learning.
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        
        # Core systems
        self._visual_engine: Optional[Any] = None
        self._learning_system: Optional[Any] = None
        self._technical_engine: Optional[Any] = None
        self._animation_engine: Optional[Any] = None
        
        # State
        self._initialized = False
        self._lock = threading.Lock()
        
        # Stats tracking
        self._stats = {
            'images_generated': 0,
            'analyses_performed': 0,
            'animations_created': 0,
            'technical_renders': 0,
            'learning_updates': 0,
            'total_processing_time': 0.0,
        }
        
        logger.info("🎨 Visual AI Manager created - SOTA 2026")
    
    async def initialize(self) -> bool:
        """Initialize all visual AI systems."""
        if self._initialized:
            return True
        
        with self._lock:
            try:
                logger.info("🎨 Initializing SOTA 2026 Visual AI Systems...")
                
                # Initialize Visual Engine
                if AI_VISUAL_ENGINE_AVAILABLE:
                    self._visual_engine = get_visual_engine(self.event_bus)
                    await self._visual_engine.initialize()
                    logger.info("✅ AI Visual Engine initialized")
                
                # Initialize Learning System
                if OLLAMA_LEARNING_AVAILABLE:
                    self._learning_system = get_learning_system(self.event_bus)
                    await self._learning_system.initialize()
                    logger.info("✅ Ollama Learning System initialized")
                
                # Initialize Technical Visualization
                if TECHNICAL_VIZ_AVAILABLE:
                    self._technical_engine = TechnicalVisualizationEngine()
                    logger.info("✅ Technical Visualization Engine initialized")
                
                # Initialize Animation Engine
                if AI_VISUAL_ENGINE_AVAILABLE:
                    self._animation_engine = SOTAAnimationEngine(self.event_bus)
                    logger.info("✅ Animation Engine initialized")
                
                # Subscribe to events
                await self._subscribe_events()
                
                self._initialized = True
                logger.info("🎨 ✅ Visual AI Manager fully initialized")
                
                # Publish initialization event
                if self.event_bus:
                    self.event_bus.publish("visual_ai.initialized", {
                        "status": self.get_status().__dict__,
                        "timestamp": datetime.now().isoformat()
                    })
                
                return True
                
            except Exception as e:
                logger.error(f"Visual AI Manager initialization failed: {e}")
                return False
    
    async def _subscribe_events(self):
        """Subscribe to relevant events from all Kingdom AI systems."""
        if not self.event_bus:
            return
        
        subscriptions = [
            # Visual requests
            ("visual.generate.request", self._handle_generate_request),
            ("visual.analyze.request", self._handle_analyze_request),
            ("visual.technical.request", self._handle_technical_request),
            ("visual.animate.request", self._handle_animate_request),
            
            # Learning events
            ("visual.feedback", self._handle_feedback),
            ("user.style.preference", self._handle_style_preference),
            
            # Cross-system integration
            ("trading.chart.request", self._handle_trading_chart),
            ("mining.visualization.request", self._handle_mining_viz),
            ("blockchain.diagram.request", self._handle_blockchain_diagram),
            ("thoth.visual.request", self._handle_thoth_visual),
            ("vr.visual.request", self._handle_vr_visual),
            
            # Sentience integration
            ("sentience.metrics.update", self._handle_sentience_update),
        ]
        
        for event_name, handler in subscriptions:
            try:
                self.event_bus.subscribe(event_name, handler)
            except Exception as e:
                logger.warning(f"Failed to subscribe to {event_name}: {e}")
    
    async def generate_image(self, prompt: str, 
                            mode: Optional[Any] = None,
                            config: Optional[Dict] = None) -> Any:
        """Generate image using SOTA 2026 AI - main public interface."""
        if not self._visual_engine:
            return VisualResult(success=False, error="Visual engine not initialized")
        
        # Convert mode string to enum if needed
        resolved_mode = None
        if VisualMode is not None:
            if mode is None:
                resolved_mode = VisualMode.TEXT_TO_IMAGE
            elif isinstance(mode, str):
                try:
                    resolved_mode = VisualMode(mode)
                except ValueError:
                    resolved_mode = VisualMode.TEXT_TO_IMAGE
            else:
                resolved_mode = mode
        
        # Build config
        if VisualConfig is None or resolved_mode is None:
            return VisualResult(success=False, error="VisualConfig not available") if VisualResult else None
        visual_config = VisualConfig(mode=resolved_mode)
        if config:
            for key, value in config.items():
                if hasattr(visual_config, key):
                    setattr(visual_config, key, value)
        
        # Generate
        result = await self._visual_engine.generate_image(prompt, visual_config)
        
        if result.success:
            self._stats['images_generated'] += 1
            self._stats['total_processing_time'] += result.generation_time
        
        return result
    
    async def analyze_image(self, image: Union[str, bytes, Any],
                           analysis_type: str = "describe") -> Dict[str, Any]:
        """Analyze image using Ollama vision."""
        if not self._visual_engine:
            return {"success": False, "error": "Visual engine not initialized"}
        
        result = await self._visual_engine.analyze_image(image, analysis_type)
        
        if result.get('success'):
            self._stats['analyses_performed'] += 1
        
        return result
    
    async def render_technical(self, prompt: str, mode: str,
                              config: Optional[Dict] = None) -> Any:
        """Render technical visualization (math, charts, diagrams)."""
        if not self._technical_engine:
            return None
        
        try:
            # Map mode string to TechnicalMode
            mode_map = {
                'function': TechnicalMode.FUNCTION_PLOT,
                'function_plot': TechnicalMode.FUNCTION_PLOT,
                'trig': TechnicalMode.TRIGONOMETRY,
                'trigonometry': TechnicalMode.TRIGONOMETRY,
                'calculus': TechnicalMode.CALCULUS,
                'integral': TechnicalMode.CALCULUS,
                'fractal': TechnicalMode.FRACTAL,
                'mandelbrot': TechnicalMode.FRACTAL,
                'sacred': TechnicalMode.SACRED_GEOMETRY,
                'sacred_geometry': TechnicalMode.SACRED_GEOMETRY,
                'flower_of_life': TechnicalMode.SACRED_GEOMETRY,
                'map': TechnicalMode.CARTOGRAPHY,
                'cartography': TechnicalMode.CARTOGRAPHY,
                'astrology': TechnicalMode.ASTROLOGY,
                'birth_chart': TechnicalMode.ASTROLOGY,
                'zodiac': TechnicalMode.ASTROLOGY,
                'calligraphy': TechnicalMode.CALLIGRAPHY,
                'text': TechnicalMode.CALLIGRAPHY,
                'math': TechnicalMode.MATHEMATICS,
                'geometry': TechnicalMode.GEOMETRY,
            }
            
            tech_mode = mode_map.get(mode.lower(), TechnicalMode.FUNCTION_PLOT)
            
            tech_config = TechnicalConfig(
                mode=tech_mode,
                width=config.get('width', 512) if config else 512,
                height=config.get('height', 512) if config else 512,
                detail_level=config.get('detail_level', 3) if config else 3,
            )
            
            image = self._technical_engine.render(prompt, tech_config)
            self._stats['technical_renders'] += 1
            
            return image
            
        except Exception as e:
            logger.error(f"Technical rendering failed: {e}")
            return None
    
    async def create_animation(self, name: str, preset: str,
                              duration_ms: int = 1000,
                              **kwargs) -> Dict:
        """Create animation with SOTA 2026 engine."""
        if not self._animation_engine:
            return {}
        
        animation = self._animation_engine.create_animation(
            name, preset, duration_ms, **kwargs
        )
        self._stats['animations_created'] += 1
        
        return animation
    
    async def process_with_learning(self, prompt: str, 
                                   task_type: str,
                                   context: Optional[Dict] = None) -> Dict[str, Any]:
        """Process request with Ollama learning system."""
        if not self._learning_system:
            return {"success": False, "error": "Learning system not initialized"}
        
        # Map task type string to enum
        try:
            task_enum = TaskType(task_type)
        except ValueError:
            task_enum = TaskType.CHAT
        
        result = await self._learning_system.process(prompt, task_enum, context)
        
        if result.get('success'):
            self._stats['learning_updates'] += 1
        
        return result
    
    def provide_feedback(self, item_id: str, feedback: Dict[str, Any]):
        """Provide feedback for learning system."""
        if self._visual_engine:
            self._visual_engine.provide_feedback(item_id, feedback)
        if self._learning_system:
            # Store feedback in learning system knowledge base
            self._learning_system._update_knowledge("visual_feedback", {
                "item_id": item_id,
                "feedback": feedback,
                "timestamp": datetime.now().isoformat()
            })
    
    # Event handlers
    async def _handle_generate_request(self, event_data: Dict):
        """Handle image generation request from event bus."""
        prompt = event_data.get('prompt', '')
        mode = event_data.get('mode', 'text_to_image')
        config = event_data.get('config', {})
        
        if prompt:
            result = await self.generate_image(prompt, mode, config)
            
            if self.event_bus:
                self.event_bus.publish("visual.generated", {
                    "success": result.success,
                    "metadata": result.metadata,
                    "error": result.error,
                    "generation_time": result.generation_time
                })
    
    async def _handle_analyze_request(self, event_data: Dict):
        """Handle image analysis request."""
        image = event_data.get('image')
        analysis_type = event_data.get('type', 'describe')
        
        if image:
            result = await self.analyze_image(image, analysis_type)
            
            if self.event_bus:
                self.event_bus.publish("visual.analyzed", result)
    
    async def _handle_technical_request(self, event_data: Dict):
        """Handle technical visualization request."""
        prompt = event_data.get('prompt', '')
        mode = event_data.get('mode', 'function')
        config = event_data.get('config', {})
        
        if prompt:
            image = await self.render_technical(prompt, mode, config)
            
            if self.event_bus and image:
                self.event_bus.publish("visual.technical.rendered", {
                    "mode": mode,
                    "prompt": prompt,
                    "success": image is not None
                })
    
    async def _handle_animate_request(self, event_data: Dict):
        """Handle animation creation request."""
        name = event_data.get('name', '')
        preset = event_data.get('preset', 'fade_in')
        duration = event_data.get('duration_ms', 1000)
        
        if name:
            animation = await self.create_animation(name, preset, duration)
            
            if self.event_bus:
                self.event_bus.publish("visual.animation.created", {
                    "name": name,
                    "preset": preset,
                    "success": bool(animation)
                })
    
    async def _handle_feedback(self, event_data: Dict):
        """Handle feedback from user."""
        item_id = event_data.get('item_id', '')
        feedback = event_data.get('feedback', {})
        
        if item_id:
            self.provide_feedback(item_id, feedback)
    
    async def _handle_style_preference(self, event_data: Dict):
        """Handle style preference update."""
        if self._visual_engine and hasattr(self._visual_engine, 'ollama_vision'):
            style = event_data.get('style', '')
            if style:
                ollama_vision = getattr(self._visual_engine, 'ollama_vision', None)
                if ollama_vision and hasattr(ollama_vision, '_style_memory'):
                    ollama_vision._style_memory['preferred_style'] = style
    
    async def _handle_trading_chart(self, event_data: Dict):
        """Generate trading-related visualization."""
        chart_type = event_data.get('chart_type', 'price')
        data = event_data.get('data', {})
        
        # Use technical engine for chart generation
        if self._technical_engine:
            prompt = f"Trading {chart_type} chart"
            image = await self.render_technical(prompt, 'function', {
                'width': 800,
                'height': 400
            })
            
            if self.event_bus and image:
                self.event_bus.publish("trading.chart.rendered", {
                    "chart_type": chart_type,
                    "success": True
                })
    
    async def _handle_mining_viz(self, event_data: Dict):
        """Generate mining-related visualization."""
        viz_type = event_data.get('viz_type', 'hashrate')
        
        if self._technical_engine:
            prompt = f"Mining {viz_type} visualization"
            image = await self.render_technical(prompt, 'function', {})
            
            if self.event_bus and image:
                self.event_bus.publish("mining.visualization.rendered", {
                    "viz_type": viz_type,
                    "success": True
                })
    
    async def _handle_blockchain_diagram(self, event_data: Dict):
        """Generate blockchain diagram."""
        diagram_type = event_data.get('diagram_type', 'network')
        
        # Generate as image
        prompt = f"Blockchain {diagram_type} diagram, network visualization"
        result = await self.generate_image(prompt, VisualMode.TEXT_TO_IMAGE, {
            'width': 800,
            'height': 600
        })
        
        if self.event_bus:
            self.event_bus.publish("blockchain.diagram.rendered", {
                "diagram_type": diagram_type,
                "success": result.success
            })
    
    async def _handle_thoth_visual(self, event_data: Dict):
        """Handle visual request from Thoth AI."""
        prompt = event_data.get('prompt', '')
        mode = event_data.get('mode', 'image')
        
        if prompt:
            # Enhance prompt with Ollama if learning system available
            if self._learning_system and self._learning_system.active:
                enhanced_result = await self._learning_system.process(
                    prompt, 
                    TaskType.IMAGE_GENERATION_PROMPT,
                    {"source": "thoth_ai"}
                )
                if enhanced_result.get('success'):
                    prompt = enhanced_result.get('response', prompt)
            
            result = await self.generate_image(prompt, mode, {})
            
            if self.event_bus:
                self.event_bus.publish("thoth.visual.rendered", {
                    "prompt": prompt,
                    "success": result.success,
                    "metadata": result.metadata
                })
    
    async def _handle_vr_visual(self, event_data: Dict):
        """Handle visual request from VR system."""
        visual_type = event_data.get('type', 'texture')
        prompt = event_data.get('prompt', '')
        
        if prompt:
            config = {
                'width': 1024,
                'height': 1024,
                'quality': 'high'
            }
            
            result = await self.generate_image(prompt, VisualMode.TEXT_TO_IMAGE, config)
            
            if self.event_bus:
                self.event_bus.publish("vr.visual.rendered", {
                    "type": visual_type,
                    "success": result.success,
                    "metadata": result.metadata
                })
    
    async def _handle_sentience_update(self, event_data: Dict):
        """Handle sentience metrics update for generation adaptation."""
        if self._visual_engine:
            score = event_data.get('score', 0.5)
            level = event_data.get('level', 'REACTIVE')
            
            # Adjust generation parameters based on sentience
            if hasattr(self._visual_engine, 'generator'):
                if score > 0.7:
                    # Higher quality for higher sentience
                    pass  # Could adjust default config
    
    def get_status(self) -> VisualAIStatus:
        """Get current status of Visual AI Manager."""
        status = VisualAIStatus(
            initialized=self._initialized,
            visual_engine_active=self._visual_engine is not None,
            learning_system_active=self._learning_system is not None and self._learning_system.active,
            technical_viz_active=self._technical_engine is not None,
            stats=self._stats.copy()
        )
        
        # Get detailed status from sub-systems
        if self._visual_engine:
            engine_status = self._visual_engine.get_status()
            status.ollama_connected = engine_status.get('ollama_active', False)
            status.available_models = engine_status.get('ollama_models', [])
            status.backends = engine_status.get('backends', {})
        
        if self._learning_system:
            learning_stats = self._learning_system.get_learning_stats()
            status.available_models = learning_stats.get('models', status.available_models)
        
        return status
    
    def get_stats(self) -> Dict[str, Any]:
        """Get generation statistics."""
        stats = self._stats.copy()
        
        if self._visual_engine:
            engine_status = self._visual_engine.get_status()
            stats.update(engine_status.get('stats', {}))
        
        if self._learning_system:
            learning_stats = self._learning_system.get_learning_stats()
            stats['learning_interactions'] = learning_stats.get('interaction_count', 0)
            stats['feedback_received'] = learning_stats.get('feedback_count', 0)
        
        return stats


# Global instance
_visual_ai_manager: Optional[VisualAIManager] = None


def get_visual_ai_manager(event_bus=None) -> VisualAIManager:
    """Get or create the global Visual AI Manager instance."""
    global _visual_ai_manager
    if _visual_ai_manager is None:
        _visual_ai_manager = VisualAIManager(event_bus)
    return _visual_ai_manager


async def initialize_visual_ai_systems(event_bus=None) -> VisualAIManager:
    """Initialize all visual AI systems - call this during app startup."""
    manager = get_visual_ai_manager(event_bus)
    await manager.initialize()
    return manager


# Export
__all__ = [
    'VisualAIManager',
    'VisualAIStatus',
    'get_visual_ai_manager',
    'initialize_visual_ai_systems',
]
