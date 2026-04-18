#!/usr/bin/env python3
"""
Creation Orchestrator - SOTA 2026 Multi-Engine Composition System
==================================================================
Unified orchestration layer that combines ALL creation engines to work
TOGETHER on a single user request.

COMBINES:
- Visual Creation Canvas (image generation - FLUX.1, SD3.5, LCM)
- Cinema Engine SOTA 2026 (video/movie generation)
- Medical Reconstruction Engine (CT/MRI → 3D models)
- Universal Animation Engine (motion, physics, particles)
- Unity MCP Integration (3D rendering, terrain, game assets)
- Unified Creative Engine (maps, designs, art styles)

EXAMPLE WORKFLOWS:
1. "Create a holographic medical heart animation"
   → Medical Engine: Generate heart 3D model
   → Animation Engine: Add holographic effect
   → Cinema Engine: Render as video
   → Unity: Display in 3D scene
   
2. "Generate a fantasy world map with animated clouds"
   → Unified Creative Engine: Generate world map
   → Animation Engine: Add cloud particles
   → Cinema Engine: Render fly-through video
   
3. "Create a cyberpunk city schematic with neon lights"
   → Unified Creative Engine: Generate city layout
   → Visual Canvas: Add neon lighting (image gen)
   → Cinema Engine: Add light animation
   → Unity: Display in 3D
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger("KingdomAI.CreationOrchestrator")


class EngineType(Enum):
    """Available creation engines - COMPLETE SOTA 2026"""
    # Original 14 engines
    VISUAL = "visual_canvas"           # Image generation (FLUX, SD3.5, LCM)
    CINEMA = "cinema"                  # Video generation
    MEDICAL = "medical"                # Medical reconstruction
    ANIMATION = "animation"            # Motion & particles
    UNITY = "unity"                    # 3D rendering
    CREATIVE = "creative"              # Maps, designs, art
    GENIE3 = "genie3"                  # 3D world generation (DeepMind Genie 3)
    BOOKTOK = "booktok"                # BookTok video storyboarding
    AI_VISUAL = "ai_visual"            # AI visual processing & enhancement
    TECHNICAL_VIZ = "technical_viz"    # Technical/math/geometry visualization
    DATA_VIZ = "data_viz"              # Universal data visualization
    DYNAMIC_RENDER = "dynamic_render"  # Universal data rendering
    REALTIME_STUDIO = "realtime_studio"  # Real-time compositing
    VIDEO_BACKENDS = "video_backends"  # SOTA video backends (Mochi, CogVideoX, etc.)
    
    # NEW SOTA 2026 Story/Movie/Game engines
    SCREENPLAY = "screenplay"          # Screenplay & narrative generation
    CHARACTER_CONSISTENCY = "character_consistency"  # Character visual/personality consistency
    STORYBOARD = "storyboard"          # Shot planning & storyboarding
    WORLD_GEN = "world_gen"            # Procedural world generation for games
    
    # NEW SOTA 2026 Design/Engineering engines
    CAD_MECHANICAL = "cad_mechanical"  # CAD + 3D Printing + STL/G-code + Slicer + Laser Engraving
    FASHION_CLOTHING = "fashion_clothing"  # Fashion design & clothing generation
    ARCHITECTURAL = "architectural"    # Architectural design & building generation
    ELECTRONICS_CIRCUIT = "electronics_circuit"  # PCB design + Manufacturing (JLCPCB/PCBWay/Voltera) + Conductive Ink
    INDUSTRIAL_PRODUCT = "industrial_product"  # Advanced Materials + Multi-Color + Full-Color Printing
    

class CompositionMode(Enum):
    """How engines work together"""
    SEQUENTIAL = "sequential"      # One after another (pipeline)
    PARALLEL = "parallel"          # All at once (merge outputs)
    LAYERED = "layered"            # Stacked layers (compositing)
    HYBRID = "hybrid"              # Mix of all


@dataclass
class EngineTask:
    """A task for a specific engine"""
    engine: EngineType
    operation: str                 # e.g., "generate_image", "reconstruct_3d"
    params: Dict[str, Any]
    input_from: Optional[str] = None  # Task ID to take input from
    output_key: str = "result"     # Key in outputs dict


@dataclass
class CreationPipeline:
    """Multi-engine creation pipeline"""
    id: str
    description: str
    tasks: List[EngineTask]
    mode: CompositionMode = CompositionMode.SEQUENTIAL
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CreationResult:
    """Result from multi-engine creation"""
    pipeline_id: str
    outputs: Dict[str, Any]        # Keyed by output_key
    final_output: Any              # Primary result
    metadata: Dict[str, Any]
    execution_time: float
    success: bool = True
    error: Optional[str] = None


class CreationOrchestrator:
    """
    Orchestrates multi-engine creation workflows.
    
    This is the "brain" that:
    1. Analyzes user requests
    2. Breaks them into engine-specific tasks
    3. Executes tasks in optimal order
    4. Combines outputs into final creation
    """
    
    def __init__(self, event_bus=None):
        """Initialize orchestrator."""
        self.event_bus = event_bus
        self._engines: Dict[EngineType, Any] = {}
        self._active_pipelines: Dict[str, CreationPipeline] = {}
        
        logger.info("🎨 CreationOrchestrator initializing...")

    # ---------------------------------------------------------------------
    # WHOLE-STUDIO ENGINE POLICY (SOTA 2026)
    # ---------------------------------------------------------------------
    def get_engine_chain_map(self) -> Dict[str, Dict[str, Any]]:
        """Authoritative mapping of each studio engine to routing purpose."""
        return {
            EngineType.VISUAL.value: {
                "role": "Concept and reference image generation",
                "when_to_use": ["design", "concept art", "reference image", "style"],
                "default_operation": "generate_image",
                "outputs": ["image_path", "concept_image"],
            },
            EngineType.CINEMA.value: {
                "role": "Final cinematic video rendering",
                "when_to_use": ["render video", "movie", "cinematic output"],
                "default_operation": "render_video",
                "outputs": ["video_path"],
            },
            EngineType.MEDICAL.value: {
                "role": "Medical reconstruction and anatomy modeling",
                "when_to_use": ["ct", "mri", "medical", "anatomy"],
                "default_operation": "reconstruct_3d",
                "outputs": ["medical_model"],
            },
            EngineType.ANIMATION.value: {
                "role": "Motion, assembly sequencing, and simulation animation",
                "when_to_use": ["animate", "motion", "assembly sequence", "particles"],
                "default_operation": "animate",
                "outputs": ["animated_sequence"],
            },
            EngineType.UNITY.value: {
                "role": "3D runtime/world export",
                "when_to_use": ["unity", "runtime", "3d scene", "game export"],
                "default_operation": "export_to_unity",
                "outputs": ["unity_scene"],
            },
            EngineType.CREATIVE.value: {
                "role": "Schematic/map/blueprint generation",
                "when_to_use": ["schematic", "blueprint", "map", "layout"],
                "default_operation": "generate_schematic",
                "outputs": ["creative_spec"],
            },
            EngineType.GENIE3.value: {
                "role": "Generative world-model synthesis",
                "when_to_use": ["interactive world", "agentic world sim", "game world"],
                "default_operation": "generate_world",
                "outputs": ["world_model"],
            },
            EngineType.BOOKTOK.value: {
                "role": "Narrative explainability and user-facing story breakdown",
                "when_to_use": ["explain", "how it works", "booktok", "walkthrough"],
                "default_operation": "explain_mechanics",
                "outputs": ["booktok_explainer"],
            },
            EngineType.AI_VISUAL.value: {
                "role": "Visual enhancement/post-processing",
                "when_to_use": ["enhance", "upscale", "cleanup", "refine image"],
                "default_operation": "enhance",
                "outputs": ["enhanced_visual"],
            },
            EngineType.TECHNICAL_VIZ.value: {
                "role": "Engineering/technical diagram and analysis visualization",
                "when_to_use": ["technical diagram", "exploded view", "math viz", "physics viz"],
                "default_operation": "render",
                "outputs": ["technical_visual"],
            },
            EngineType.DATA_VIZ.value: {
                "role": "Data-centric charting and dashboards",
                "when_to_use": ["chart", "graph", "dashboard", "timeseries visualization"],
                "default_operation": "render",
                "outputs": ["data_visual"],
            },
            EngineType.DYNAMIC_RENDER.value: {
                "role": "Dynamic render backend composition",
                "when_to_use": ["real-time overlay", "dynamic compositing"],
                "default_operation": "render",
                "outputs": ["dynamic_render"],
            },
            EngineType.REALTIME_STUDIO.value: {
                "role": "Realtime compositing/playback control",
                "when_to_use": ["live preview", "studio playback"],
                "default_operation": "compose",
                "outputs": ["realtime_scene"],
            },
            EngineType.VIDEO_BACKENDS.value: {
                "role": "Alternative generative video backends",
                "when_to_use": ["backend selection", "specific video model request"],
                "default_operation": "render_video",
                "outputs": ["backend_video"],
            },
            EngineType.SCREENPLAY.value: {
                "role": "Long-form narrative screenplay planning",
                "when_to_use": ["screenplay", "script", "scene writing"],
                "default_operation": "generate_screenplay",
                "outputs": ["screenplay"],
            },
            EngineType.CHARACTER_CONSISTENCY.value: {
                "role": "Character identity consistency",
                "when_to_use": ["consistent character", "same person across scenes"],
                "default_operation": "generate_character_sheets",
                "outputs": ["character_sheet"],
            },
            EngineType.STORYBOARD.value: {
                "role": "Shot planning and animatic",
                "when_to_use": ["storyboard", "animatic", "shot list"],
                "default_operation": "plan_storyboard",
                "outputs": ["storyboard"],
            },
            EngineType.WORLD_GEN.value: {
                "role": "Procedural 3D world generation",
                "when_to_use": ["generate world", "terrain", "level generation"],
                "default_operation": "generate_world",
                "outputs": ["world_gen"],
            },
            EngineType.CAD_MECHANICAL.value: {
                "role": "Parametric CAD, assembly graph, blueprint/schematic, fabrication exports",
                "when_to_use": ["mechanical design", "cad", "exploded assembly", "fit and function", "blueprint", "schematic", "technical drawing", "dxf"],
                "default_operation": "generate_cad",
                "outputs": ["cad_model", "stl_file"],
            },
            EngineType.FASHION_CLOTHING.value: {
                "role": "Garment and pattern design",
                "when_to_use": ["fashion", "clothing", "pattern"],
                "default_operation": "generate_pattern",
                "outputs": ["pattern", "garment"],
            },
            EngineType.ARCHITECTURAL.value: {
                "role": "Architecture planning and building layout",
                "when_to_use": ["house", "architecture", "floor plan"],
                "default_operation": "generate_floor_plan",
                "outputs": ["architectural_plan"],
            },
            EngineType.ELECTRONICS_CIRCUIT.value: {
                "role": "Circuit/PCB synthesis and manufacturing data",
                "when_to_use": ["pcb", "circuit", "electronics"],
                "default_operation": "generate_circuit",
                "outputs": ["circuit", "gerber"],
            },
            EngineType.INDUSTRIAL_PRODUCT.value: {
                "role": "Industrial/product concept and material selection",
                "when_to_use": ["industrial product", "materials", "consumer device"],
                "default_operation": "generate_product",
                "outputs": ["product_design"],
            },
        }

    def _build_whole_studio_chain(self, request: str) -> Optional[CreationPipeline]:
        """Semantic whole-studio planner for any prompt."""
        r = (request or "").lower()
        tasks: List[EngineTask] = []
        pid = f"pipeline_{int(time.time() * 1000)}"

        wants_cad = any(k in r for k in ("cad", "mechanical", "engineering", "fit", "tolerance", "assembly", "exploded", "supercar", "machine"))
        wants_blueprint = any(k in r for k in ("blueprint", "schematic", "technical drawing", "dxf", "dimensioned", "orthographic", "floor plan", "assembly diagram"))
        wants_visual_design = any(k in r for k in ("design", "create", "make", "concept", "draw", "image", "look", "style", "shape", "outline"))
        wants_video = any(k in r for k in ("video", "movie", "cinematic", "render", "animation", "animate", "moving", "motion", "flow visualization"))
        wants_explain = any(k in r for k in ("explain", "how it works", "booktok", "describe", "breakdown"))
        wants_physics = any(k in r for k in ("physics", "simulation", "dynamics", "cfd", "stress", "calibrate"))
        wants_electronics = any(k in r for k in ("pcb", "circuit", "electronics"))
        wants_arch = any(k in r for k in ("architecture", "building", "house", "floor plan"))
        wants_fashion = any(k in r for k in ("fashion", "garment", "clothing"))
        wants_story = any(k in r for k in ("screenplay", "storyboard", "script", "narrative", "character"))
        wants_world = any(k in r for k in ("world", "terrain", "level", "game"))
        forced_unified = any(k in r for k in ("all engines", "whole studio", "unified pipeline", "use all tools"))

        # Domain-specialized direct chains first.
        if wants_electronics:
            tasks.extend([
                EngineTask(EngineType.ELECTRONICS_CIRCUIT, "generate_circuit", {"description": request, "optimize_for": "size"}, output_key="circuit"),
                EngineTask(EngineType.TECHNICAL_VIZ, "render", {"prompt": request, "mode": "geometry"}, input_from="circuit", output_key="technical_visual"),
            ])
            if wants_video or forced_unified:
                tasks.extend([
                    EngineTask(EngineType.ANIMATION, "animate", {"style": "flow_visualization", "frames": 180, "fps": 24}, input_from="technical_visual", output_key="animated_sequence"),
                    EngineTask(EngineType.CINEMA, "render_video", {"quality": "high", "fps": 24}, input_from="animated_sequence", output_key="final"),
                ])
            else:
                tasks.append(EngineTask(EngineType.TECHNICAL_VIZ, "render", {"prompt": request, "mode": "geometry"}, input_from="circuit", output_key="final"))
        elif wants_arch:
            tasks.append(EngineTask(EngineType.ARCHITECTURAL, "generate_floor_plan", {"requirements": request, "building_type": "auto"}, output_key="architectural_plan"))
            if wants_video or forced_unified:
                tasks.extend([
                    EngineTask(EngineType.UNITY, "export_to_unity", {"world": None}, input_from="architectural_plan", output_key="unity_scene"),
                    EngineTask(EngineType.CINEMA, "render_video", {"quality": "high", "fps": 24}, input_from="unity_scene", output_key="final"),
                ])
            else:
                tasks.append(EngineTask(EngineType.UNITY, "export_to_unity", {"world": None}, input_from="architectural_plan", output_key="final"))
        elif wants_fashion:
            tasks.extend([
                EngineTask(EngineType.FASHION_CLOTHING, "generate_pattern", {"description": request, "garment_type": "auto"}, output_key="pattern"),
                EngineTask(EngineType.FASHION_CLOTHING, "generate_3d_garment", {"description": request}, input_from="pattern", output_key="garment"),
            ])
            if wants_video or forced_unified:
                tasks.extend([
                    EngineTask(EngineType.ANIMATION, "animate", {"style": "cloth_drape", "frames": 160, "fps": 24}, input_from="garment", output_key="animated_sequence"),
                    EngineTask(EngineType.CINEMA, "render_video", {"quality": "high", "fps": 24}, input_from="animated_sequence", output_key="final"),
                ])
            else:
                tasks.append(EngineTask(EngineType.VISUAL, "enhance_image", {"prompt": request, "style": "fashion_editorial"}, input_from="garment", output_key="final"))
        elif wants_story:
            tasks.extend([
                EngineTask(EngineType.SCREENPLAY, "generate_screenplay", {"premise": request, "genre": "auto", "num_scenes": 10}, output_key="screenplay"),
                EngineTask(EngineType.STORYBOARD, "plan_storyboard", {"screenplay": None, "style": "cinematic"}, input_from="screenplay", output_key="storyboard"),
            ])
            if wants_video or forced_unified:
                tasks.append(EngineTask(EngineType.CINEMA, "render_multi_shot_video", {"storyboard": None}, input_from="storyboard", output_key="final"))
            else:
                tasks.append(EngineTask(EngineType.STORYBOARD, "generate_animatic", {"storyboard": None}, input_from="storyboard", output_key="final"))
        elif wants_world:
            tasks.extend([
                EngineTask(EngineType.WORLD_GEN, "generate_world", {"description": request, "scale": "auto", "type": "auto"}, output_key="world"),
                EngineTask(EngineType.UNITY, "export_to_unity", {"world": None}, input_from="world", output_key="unity_scene"),
            ])
            if wants_video or forced_unified:
                tasks.append(EngineTask(EngineType.CINEMA, "render_video", {"quality": "high", "fps": 24}, input_from="unity_scene", output_key="final"))
            else:
                tasks.append(EngineTask(EngineType.UNITY, "export_to_unity", {"world": None}, input_from="world", output_key="final"))
        else:
            # General whole-studio design chain (visual -> CAD -> technical -> animation -> cinema -> explain).
            if wants_visual_design or wants_cad or wants_video or wants_physics or forced_unified:
                tasks.append(EngineTask(EngineType.VISUAL, "generate_image", {"prompt": request}, output_key="concept_image"))
            if wants_cad or wants_physics or forced_unified:
                tasks.append(
                    EngineTask(
                        EngineType.CAD_MECHANICAL,
                        "generate_cad_from_image" if (wants_visual_design or forced_unified) else "generate_cad",
                        {"description": request},
                        input_from="concept_image" if (wants_visual_design or forced_unified) else None,
                        output_key="cad_model",
                    )
                )
                tasks.append(EngineTask(EngineType.CAD_MECHANICAL, "export_stl", {}, input_from="cad_model", output_key="stl_file"))
                if wants_blueprint:
                    tasks.append(EngineTask(EngineType.CAD_MECHANICAL, "generate_blueprint", {"description": request, "format": "dxf"}, input_from="cad_model", output_key="blueprint_dxf"))
                    tasks.append(EngineTask(EngineType.CAD_MECHANICAL, "generate_schematic", {"description": request}, input_from="cad_model", output_key="schematic_svg"))
                tasks.append(EngineTask(EngineType.TECHNICAL_VIZ, "render", {"mode": "engineering_exploded", "prompt": request}, input_from="stl_file", output_key="technical_visual"))
                if wants_physics or forced_unified:
                    tasks.append(EngineTask(EngineType.ANIMATION, "animate", {"style": "simulation", "frames": 180, "fps": 24}, input_from="technical_visual", output_key="sim_visual"))
            if wants_video or forced_unified or wants_cad:
                source_key = "sim_visual" if ("sim_visual" in [t.output_key for t in tasks]) else ("technical_visual" if ("technical_visual" in [t.output_key for t in tasks]) else "concept_image")
                tasks.append(EngineTask(EngineType.ANIMATION, "animate", {"style": "assembly_dynamics", "frames": 180, "fps": 24}, input_from=source_key, output_key="animated_sequence"))
                tasks.append(EngineTask(EngineType.CINEMA, "render_video", {"quality": "high", "fps": 24}, input_from="animated_sequence", output_key="final"))
            elif tasks:
                tasks.append(EngineTask(EngineType.VISUAL, "enhance_image", {"prompt": request, "style": "detailed"}, input_from=tasks[-1].output_key, output_key="final"))

        if not tasks:
            return None

        # Optional explainability for all domains when requested.
        if wants_explain or forced_unified:
            tasks.append(
                EngineTask(
                    engine=EngineType.BOOKTOK,
                    operation="explain_mechanics",
                    params={"prompt": request},
                    input_from=tasks[-1].output_key,
                    output_key="booktok_explainer",
                )
            )
            tasks.append(
                EngineTask(
                    engine=EngineType.BOOKTOK,
                    operation="generate_storyboard",
                    params={"prompt": request},
                    input_from="booktok_explainer",
                    output_key="final",
                )
            )

        return CreationPipeline(
            id=pid,
            description=request,
            tasks=tasks,
            mode=CompositionMode.SEQUENTIAL,
            metadata={
                "routing_policy": "whole_studio_semantic_v1",
                "engine_chain_map": self.get_engine_chain_map(),
                "original_request": request,
            },
        )
        
    def register_engine(self, engine_type: EngineType, engine_instance: Any):
        """Register an engine for orchestration."""
        self._engines[engine_type] = engine_instance
        logger.info(f"✅ Registered engine: {engine_type.value}")
    
    def _lazy_load_engines(self):
        """Lazy load all engines on first use."""
        if self._engines:
            return  # Already loaded
        
        logger.info("🔄 Lazy-loading ALL creation engines...")
        
        # CORE ENGINES (Original 6)
        # ===========================
        
        # Load Visual Canvas
        try:
            from gui.widgets.visual_creation_canvas import ImageGenerationWorker
            self._engines[EngineType.VISUAL] = ImageGenerationWorker(self.event_bus)
            logger.info("✅ Visual Canvas engine loaded")
        except Exception as e:
            logger.warning(f"⚠️ Visual Canvas engine failed: {e}")
        
        # Load Cinema Engine
        try:
            # Support canonical class name in cinema engine module.
            from core.cinema_engine_sota_2026 import CinemaEngineSOTA2026
            self._engines[EngineType.CINEMA] = CinemaEngineSOTA2026(event_bus=self.event_bus)
            logger.info("✅ Cinema Engine loaded")
        except Exception as e:
            logger.warning(f"⚠️ Cinema Engine failed: {e}")
        
        # Load Medical Reconstruction
        try:
            from core.medical_reconstruction_engine import MedicalReconstructionEngine
            self._engines[EngineType.MEDICAL] = MedicalReconstructionEngine()
            logger.info("✅ Medical Engine loaded")
        except Exception as e:
            logger.warning(f"⚠️ Medical Engine failed: {e}")
        
        # Load Animation Engine
        try:
            from core.universal_animation_engine import UniversalAnimationEngine
            self._engines[EngineType.ANIMATION] = UniversalAnimationEngine(event_bus=self.event_bus)
            logger.info("✅ Animation Engine loaded")
        except Exception as e:
            logger.warning(f"⚠️ Animation Engine failed: {e}")
        
        # Load Unity Integration
        try:
            from core.unity_mcp_integration import UnityMCPIntegration
            self._engines[EngineType.UNITY] = UnityMCPIntegration()
            logger.info("✅ Unity Engine loaded")
        except Exception as e:
            logger.warning(f"⚠️ Unity Engine failed: {e}")
        
        # Load Unified Creative Engine (SINGLETON - shared with Creation Studio)
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                self._engines[EngineType.CREATIVE] = self.event_bus.get_component('unified_creative_engine', silent=True)
            if self._engines.get(EngineType.CREATIVE) is None:
                from core.unified_creative_engine import get_unified_creative_engine
                self._engines[EngineType.CREATIVE] = get_unified_creative_engine(event_bus=self.event_bus)
                if self.event_bus and hasattr(self.event_bus, 'register_component'):
                    self.event_bus.register_component('unified_creative_engine', self._engines[EngineType.CREATIVE])
            logger.info("✅ Creative Engine loaded (shared singleton)")
        except Exception as e:
            logger.warning(f"⚠️ Creative Engine failed: {e}")
        
        # EXTENDED ENGINES (New 8)
        # ==========================
        
        # Load Genie 3 World Model
        try:
            from core.genie3_world_model import Genie3WorldModel
            self._engines[EngineType.GENIE3] = Genie3WorldModel(event_bus=self.event_bus)
            logger.info("✅ Genie3 World Model engine loaded (3D world generation)")
        except Exception as e:
            logger.warning(f"⚠️ Genie3 engine failed: {e}")
        
        # Load BookTok Aggregator
        try:
            from core.booktok_context_aggregator import BookTokContextAggregator
            self._engines[EngineType.BOOKTOK] = BookTokContextAggregator(event_bus=self.event_bus)
            logger.info("✅ BookTok engine loaded (video storyboarding)")
        except Exception as e:
            logger.warning(f"⚠️ BookTok engine failed: {e}")
        
        # Load AI Visual Engine
        try:
            from core.ai_visual_engine import AIVisualEngine
            self._engines[EngineType.AI_VISUAL] = AIVisualEngine(event_bus=self.event_bus)
            logger.info("✅ AI Visual Engine loaded (AI processing & enhancement)")
        except Exception as e:
            logger.warning(f"⚠️ AI Visual engine failed: {e}")
        
        # Load Technical Visualization Engine
        try:
            from gui.widgets.technical_visualization_engine import TechnicalVisualizationEngine
            self._engines[EngineType.TECHNICAL_VIZ] = TechnicalVisualizationEngine(event_bus=self.event_bus)
            logger.info("✅ Technical Visualization engine loaded (math/geometry/charts)")
        except Exception as e:
            logger.warning(f"⚠️ Technical Viz engine failed: {e}")
        
        # Load Universal Data Visualizer
        try:
            from core.universal_data_visualizer import UniversalDataVisualizer
            self._engines[EngineType.DATA_VIZ] = UniversalDataVisualizer(event_bus=self.event_bus)
            logger.info("✅ Data Visualizer loaded (sensor data → visuals)")
        except Exception as e:
            logger.warning(f"⚠️ Data Viz engine failed: {e}")
        
        # Load Dynamic Renderer
        try:
            from core.dynamic_renderer import DynamicRenderer
            self._engines[EngineType.DYNAMIC_RENDER] = DynamicRenderer()
            logger.info("✅ Dynamic Renderer loaded (universal data rendering)")
        except Exception as e:
            logger.warning(f"⚠️ Dynamic Renderer failed: {e}")
        
        # Load Realtime Creative Studio
        try:
            from core.realtime_creative_studio import RealtimeCreativeStudio
            self._engines[EngineType.REALTIME_STUDIO] = RealtimeCreativeStudio(event_bus=self.event_bus)
            logger.info("✅ Realtime Studio loaded (live compositing)")
        except Exception as e:
            logger.warning(f"⚠️ Realtime Studio failed: {e}")
        
        # Load Video Backends (Mochi, CogVideoX, LTXVideo, etc.)
        try:
            from gui.widgets.video_backends_sota_2026 import (
                Mochi1Backend, CogVideoXBackend, LTXVideoBackend,
                SVDXTBackend, AnimateLCMBackend, HunyuanVideoBackend
            )
            self._engines[EngineType.VIDEO_BACKENDS] = {
                'mochi1': Mochi1Backend(),
                'cogvideox': CogVideoXBackend(),
                'ltxvideo': LTXVideoBackend(),
                'svd_xt': SVDXTBackend(),
                'animatelcm': AnimateLCMBackend(),
                'hunyuan': HunyuanVideoBackend()
            }
            logger.info("✅ Video Backends loaded (Mochi, CogVideoX, LTXVideo, SVD-XT, AnimateLCM, Hunyuan)")
        except Exception as e:
            logger.warning(f"⚠️ Video Backends failed: {e}")
        
        # NEW SOTA 2026 STORY/MOVIE/GAME ENGINES
        # ========================================
        
        # Load Screenplay & Narrative Engine
        try:
            from core.screenplay_narrative_engine import get_screenplay_engine
            self._engines[EngineType.SCREENPLAY] = get_screenplay_engine(event_bus=self.event_bus)
            logger.info("✅ Screenplay Engine loaded (narrative generation, story structure)")
        except Exception as e:
            logger.warning(f"⚠️ Screenplay Engine failed: {e}")
        
        # Load Character Consistency Engine
        try:
            from core.character_consistency_engine import get_character_engine
            self._engines[EngineType.CHARACTER_CONSISTENCY] = get_character_engine(event_bus=self.event_bus)
            logger.info("✅ Character Consistency Engine loaded (visual/personality consistency)")
        except Exception as e:
            logger.warning(f"⚠️ Character Consistency Engine failed: {e}")
        
        # Load Storyboard Planner
        try:
            from core.storyboard_planner import get_storyboard_planner
            self._engines[EngineType.STORYBOARD] = get_storyboard_planner(event_bus=self.event_bus)
            logger.info("✅ Storyboard Planner loaded (shot planning, cinematic visualization)")
        except Exception as e:
            logger.warning(f"⚠️ Storyboard Planner failed: {e}")
        
        # Load World Generation Engine
        try:
            from core.world_generation_engine import get_world_engine
            self._engines[EngineType.WORLD_GEN] = get_world_engine(event_bus=self.event_bus)
            logger.info("✅ World Generation Engine loaded (procedural worlds for games)")
        except Exception as e:
            logger.warning(f"⚠️ World Generation Engine failed: {e}")
        
        # NEW SOTA 2026 DESIGN/ENGINEERING ENGINES
        # ==========================================
        
        # Load CAD & Mechanical Engineering Engine (ENHANCED SOTA 2026)
        # Now includes: 3D printing (STL export, G-code generation),
        # slicer profiles (OrcaSlicer, PrusaSlicer, Cura, Bambu Studio),
        # printer control (OctoPrint, Klipper/Moonraker),
        # laser engraving G-code, CadQuery/SolidPython parametric CAD,
        # STL model repositories (Thingiverse, Printables, MyMiniFactory),
        # multi-color printing (Bambu AMS, Prusa MMU3, Mosaic Palette 3),
        # OpenVINO edge AI for print monitoring
        try:
            from core.cad_mechanical_engineering_engine import get_cad_engine
            self._engines[EngineType.CAD_MECHANICAL] = get_cad_engine(event_bus=self.event_bus)
            logger.info("✅ CAD Engine loaded (3D printing + STL/G-code + laser + slicers)")
        except Exception as e:
            logger.warning(f"⚠️ CAD Engine failed: {e}")
        
        # Load Fashion & Clothing Design Engine
        try:
            from core.fashion_clothing_design_engine import get_fashion_engine
            self._engines[EngineType.FASHION_CLOTHING] = get_fashion_engine(event_bus=self.event_bus)
            logger.info("✅ Fashion & Clothing Design Engine loaded (sewing patterns, virtual try-on)")
        except Exception as e:
            logger.warning(f"⚠️ Fashion Engine failed: {e}")
        
        # Load Architectural Design Engine
        try:
            from core.architectural_design_engine import get_architectural_engine
            self._engines[EngineType.ARCHITECTURAL] = get_architectural_engine(event_bus=self.event_bus)
            logger.info("✅ Architectural Design Engine loaded (floor plans, building generation)")
        except Exception as e:
            logger.warning(f"⚠️ Architectural Engine failed: {e}")
        
        # Load Electronics & Circuit Design Engine (ENHANCED SOTA 2026)
        # Now includes: PCB manufacturing (JLCPCB, PCBWay APIs), Voltera V-One/NOVA,
        # BotFactory SV2, Electroninks CircuitJet, conductive ink database,
        # KiCad 9.0 Python API, EasyEDA integration, Gerber generation
        try:
            from core.electronics_circuit_design_engine import get_electronics_engine
            self._engines[EngineType.ELECTRONICS_CIRCUIT] = get_electronics_engine(event_bus=self.event_bus)
            logger.info("✅ Electronics Engine loaded (PCB design + manufacturing + conductive ink)")
        except Exception as e:
            logger.warning(f"⚠️ Electronics Engine failed: {e}")
        
        # Load Industrial Product Design Engine (ENHANCED SOTA 2026)
        # Now includes: Advanced materials database (26+ materials),
        # metal filaments (BASF Ultrafuse 316L, 17-4PH, copper, bronze),
        # carbon fiber composites (PLA-CF, PETG-CF, PA-CF, PEEK-CF),
        # high-performance polymers (PEEK, PEKK, PEI/ULTEM),
        # full-color 3D printing (Stratasys J55, HP MJF 580, Mimaki),
        # material recommendation AI, manufacturing method advisor
        try:
            from core.industrial_product_design_engine import get_industrial_engine
            self._engines[EngineType.INDUSTRIAL_PRODUCT] = get_industrial_engine(event_bus=self.event_bus)
            logger.info("✅ Industrial Engine loaded (materials DB + full-color + manufacturing)")
        except Exception as e:
            logger.warning(f"⚠️ Industrial Design Engine failed: {e}")
        
        logger.info(f"✅ Loaded {len(self._engines)}/23 creation engines")
        logger.info("   ENHANCED SOTA 2026 capabilities:")
        logger.info("   - CAD Engine: 3D printing, STL/G-code, OrcaSlicer/PrusaSlicer/Cura, laser engraving")
        logger.info("   - Electronics Engine: PCB mfg (JLCPCB/PCBWay/Voltera), conductive ink, KiCad 9.0")
        logger.info("   - Industrial Engine: 26+ materials, metal/CF/PEEK, full-color printing")
    
    async def execute_pipeline(self, pipeline: CreationPipeline) -> CreationResult:
        """Execute a multi-engine creation pipeline."""
        start_time = time.time()
        self._lazy_load_engines()
        
        logger.info(f"🎬 Executing pipeline: {pipeline.description}")
        logger.info(f"   Mode: {pipeline.mode.value}, Tasks: {len(pipeline.tasks)}")
        
        self._active_pipelines[pipeline.id] = pipeline
        outputs = {}
        
        try:
            if pipeline.mode == CompositionMode.SEQUENTIAL:
                # Execute tasks one after another
                for i, task in enumerate(pipeline.tasks):
                    logger.info(f"🔹 Task {i+1}/{len(pipeline.tasks)}: {task.engine.value} - {task.operation}")
                    result = await self._execute_task(task, outputs)
                    outputs[task.output_key] = result
                    
                    # Publish progress
                    if self.event_bus:
                        self.event_bus.publish("creation.pipeline.progress", {
                            "pipeline_id": pipeline.id,
                            "progress": int((i + 1) / len(pipeline.tasks) * 100),
                            "current_task": task.operation
                        })
            
            elif pipeline.mode == CompositionMode.PARALLEL:
                # Execute all tasks concurrently
                tasks = [self._execute_task(task, outputs) for task in pipeline.tasks]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for task, result in zip(pipeline.tasks, results):
                    if isinstance(result, Exception):
                        logger.error(f"Task {task.operation} failed: {result}")
                    else:
                        outputs[task.output_key] = result
            
            elif pipeline.mode == CompositionMode.LAYERED:
                # Execute tasks and composite layers
                layers = []
                for task in pipeline.tasks:
                    result = await self._execute_task(task, outputs)
                    outputs[task.output_key] = result
                    layers.append(result)
                
                # Composite all layers
                final = self._composite_layers(layers)
                outputs['composite'] = final
            
            elif pipeline.mode == CompositionMode.HYBRID:
                # Custom execution order based on dependencies
                final = await self._execute_hybrid(pipeline, outputs)
                outputs['final'] = final
            
            # Determine final output
            final_output = outputs.get('final') or outputs.get(pipeline.tasks[-1].output_key)
            
            execution_time = time.time() - start_time
            logger.info(f"✅ Pipeline complete in {execution_time:.2f}s")
            
            # Publish completion
            if self.event_bus:
                self.event_bus.publish("creation.pipeline.complete", {
                    "pipeline_id": pipeline.id,
                    "execution_time": execution_time,
                    "outputs": list(outputs.keys())
                })
            
            return CreationResult(
                pipeline_id=pipeline.id,
                outputs=outputs,
                final_output=final_output,
                metadata=pipeline.metadata,
                execution_time=execution_time,
                success=True
            )
        
        except Exception as e:
            logger.error(f"❌ Pipeline execution failed: {e}", exc_info=True)
            if self.event_bus:
                self.event_bus.publish("creation.pipeline.progress", {
                    "pipeline_id": pipeline.id,
                    "progress": 0,
                    "current_task": f"Failed: {str(e)[:80]}"
                })
            try:
                import torch, gc
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
            except Exception:
                pass
            return CreationResult(
                pipeline_id=pipeline.id,
                outputs=outputs,
                final_output=None,
                metadata=pipeline.metadata,
                execution_time=time.time() - start_time,
                success=False,
                error=str(e)
            )
        
        finally:
            self._active_pipelines.pop(pipeline.id, None)
    
    async def _execute_task(self, task: EngineTask, outputs: Dict[str, Any]) -> Any:
        """Execute a single engine task."""
        engine = self._engines.get(task.engine)
        if not engine:
            raise ValueError(f"Engine {task.engine.value} not loaded")
        
        # Get input if specified
        input_data = None
        if task.input_from and task.input_from in outputs:
            input_data = outputs[task.input_from]
        
        # Execute operation
        if task.engine == EngineType.VISUAL:
            return await self._execute_visual_task(engine, task, input_data)
        elif task.engine == EngineType.CINEMA:
            return await self._execute_cinema_task(engine, task, input_data)
        elif task.engine == EngineType.MEDICAL:
            return await self._execute_medical_task(engine, task, input_data)
        elif task.engine == EngineType.ANIMATION:
            return await self._execute_animation_task(engine, task, input_data)
        elif task.engine == EngineType.UNITY:
            return await self._execute_unity_task(engine, task, input_data)
        elif task.engine == EngineType.CREATIVE:
            return await self._execute_creative_task(engine, task, input_data)
        elif task.engine == EngineType.CAD_MECHANICAL:
            return await self._execute_cad_task(engine, task, input_data)
        elif task.engine == EngineType.TECHNICAL_VIZ:
            return await self._execute_technical_viz_task(engine, task, input_data)
        elif task.engine == EngineType.ELECTRONICS_CIRCUIT:
            return await self._execute_electronics_task(engine, task, input_data)
        elif task.engine == EngineType.INDUSTRIAL_PRODUCT:
            return await self._execute_industrial_task(engine, task, input_data)
        elif task.engine == EngineType.BOOKTOK:
            return await self._execute_booktok_task(engine, task, input_data)
        else:
            # Generic engine execution for remaining engines
            return await self._execute_generic_task(engine, task, input_data)
    
    async def _execute_visual_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute visual canvas task - uses AIVisualEngine or UnifiedCreativeEngine for real image generation."""
        if isinstance(input_data, dict) and input_data.get('image_path'):
            return {"type": "image", "path": input_data['image_path'], "image_path": input_data['image_path'], "from_creative": True}
        prompt = task.params.get('prompt', '') or (input_data.get('prompt', '') if isinstance(input_data, dict) else '')
        if not prompt and isinstance(input_data, dict):
            prompt = input_data.get('description', '') or input_data.get('prompt', '')
        if not prompt:
            prompt = "creative artwork"
        try:
            ai_visual = self._engines.get(EngineType.AI_VISUAL) if hasattr(self, '_engines') else None
            if ai_visual and hasattr(ai_visual, 'generate_image'):
                try:
                    visual_result = await ai_visual.generate_image(prompt)
                    if getattr(visual_result, 'success', False) and getattr(visual_result, 'image', None):
                        from pathlib import Path
                        from PIL import Image
                        exports_dir = Path(__file__).parent.parent / "exports" / "ai_creations"
                        exports_dir.mkdir(parents=True, exist_ok=True)
                        out_path = exports_dir / f"orchestrator_{int(time.time() * 1000)}.png"
                        img = visual_result.image
                        (img.save(str(out_path)) if hasattr(img, 'save') else Image.fromarray(img).save(str(out_path)))
                        return {"type": "image", "path": str(out_path), "image_path": str(out_path), "prompt": prompt}
                    elif getattr(visual_result, 'error', None):
                        logger.warning(f"AIVisualEngine returned error: {visual_result.error}")
                except asyncio.TimeoutError:
                    logger.error("AIVisualEngine timed out after 180s")
                    try:
                        import torch, gc
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                        gc.collect()
                    except Exception:
                        pass
                except RuntimeError as cuda_err:
                    if "out of memory" in str(cuda_err).lower():
                        logger.error(f"CUDA OOM in visual task: {cuda_err}")
                        try:
                            import torch, gc
                            torch.cuda.empty_cache()
                            gc.collect()
                        except Exception:
                            pass
                    else:
                        logger.debug(f"AIVisualEngine RuntimeError: {cuda_err}")
                except Exception as e:
                    logger.debug(f"AIVisualEngine fallback: {e}")
            creative = self._engines.get(EngineType.CREATIVE) if hasattr(self, '_engines') else None
            if creative and hasattr(creative, 'create'):
                result = creative.create(prompt)
                if result.get('success') and result.get('image_path'):
                    return {"type": "image", "path": result['image_path'], "image_path": result['image_path'], "prompt": prompt}
            return {"type": "image", "path": "", "prompt": prompt, "error": "No image engine available"}
        except Exception as e:
            logger.warning(f"Visual task failed: {e}")
            return {"type": "image", "path": "", "prompt": prompt, "error": str(e)}
    
    async def _execute_cinema_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute cinema engine task (video generation)."""
        logger.info("🎬 Cinema task: generating video")
        try:
            from core.cinema_engine_sota_2026 import CinemaEngineSOTA2026
            cinema = CinemaEngineSOTA2026()
            prompt = task.params.get('prompt', '') or (input_data.get('prompt', '') if isinstance(input_data, dict) else '')
            frames = task.params.get('frames', 120)
            if hasattr(cinema, 'generate_video'):
                result = cinema.generate_video(prompt=prompt, frames=frames)
                if isinstance(result, dict) and result.get('success'):
                    return {"type": "video", "path": result.get('path', ''), "frames": frames}
            if hasattr(cinema, 'generate'):
                result = cinema.generate(prompt=prompt, num_frames=frames)
                if isinstance(result, dict):
                    return {"type": "video", "path": result.get('path', result.get('video_path', '')), "frames": frames}
        except Exception as e:
            logger.warning("CinemaEngine execution failed: %s", e)
        return {"type": "video", "path": "", "frames": task.params.get('frames', 120), "error": "Cinema engine unavailable"}

    async def _execute_medical_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute medical reconstruction task."""
        logger.info("🏥 Medical task: 3D reconstruction")
        try:
            from core.medical_reconstruction_engine import MedicalReconstructionEngine
            med = MedicalReconstructionEngine()
            scan_data = task.params.get('scan_data') or (input_data if isinstance(input_data, dict) else {})
            if hasattr(med, 'reconstruct'):
                result = med.reconstruct(scan_data)
                if isinstance(result, dict):
                    return {"type": "3d_model", **result}
        except Exception as e:
            logger.warning("MedicalReconstruction execution failed: %s", e)
        return {"type": "3d_model", "vertices": [], "faces": [], "error": "Medical engine unavailable"}

    async def _execute_animation_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute animation engine task."""
        logger.info("✨ Animation task: adding motion")
        try:
            from core.universal_animation_engine import UniversalAnimationEngine
            anim = UniversalAnimationEngine()
            prompt = task.params.get('prompt', '') or (input_data.get('prompt', '') if isinstance(input_data, dict) else '')
            frames = task.params.get('frames', 60)
            fps = task.params.get('fps', 30)
            if hasattr(anim, 'animate'):
                result = anim.animate(prompt=prompt, frames=frames, fps=fps)
                if isinstance(result, dict):
                    return {"type": "animation", **result}
            if hasattr(anim, 'generate'):
                result = anim.generate(prompt=prompt, num_frames=frames, fps=fps)
                if isinstance(result, dict):
                    return {"type": "animation", **result}
        except Exception as e:
            logger.warning("AnimationEngine execution failed: %s", e)
        return {"type": "animation", "frames": task.params.get('frames', 60), "fps": task.params.get('fps', 30), "error": "Animation engine unavailable"}

    async def _execute_unity_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute Unity integration task."""
        logger.info("🎮 Unity task: 3D rendering")
        try:
            from core.unity_mcp_integration import UnityMCPIntegration
            unity = UnityMCPIntegration()
            prompt = task.params.get('prompt', '') or (input_data.get('prompt', '') if isinstance(input_data, dict) else '')
            if hasattr(unity, 'create_scene'):
                result = unity.create_scene(prompt=prompt)
                if isinstance(result, dict):
                    return {"type": "unity_scene", **result}
        except Exception as e:
            logger.warning("Unity integration failed: %s", e)
        return {"type": "unity_scene", "scene_id": "", "error": "Unity not available"}
    
    async def _execute_creative_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute unified creative engine task - maps, art, schematics."""
        logger.info("🎨 Creative task: generating art/map/design")
        prompt = task.params.get('prompt', '') or (input_data.get('prompt', '') if isinstance(input_data, dict) else '')
        if not prompt and isinstance(input_data, dict):
            prompt = input_data.get('description', '') or input_data.get('prompt', '')
        if not prompt:
            prompt = task.params.get('description', '') or "creative design"
        try:
            result = engine.create(prompt, **{k: v for k, v in task.params.items() if k not in ('prompt',)})
            if result.get('success'):
                image_path = result.get('image_path') or result.get('output_path')
                if image_path:
                    return {"type": "creative", "path": image_path, "image_path": image_path, **result}
                return {"type": "creative", **result}
            return {"type": "creative", "error": result.get('error', 'Unknown'), "success": False}
        except Exception as e:
            logger.warning(f"Creative engine task failed: {e}")
            return {"type": "creative", "error": str(e), "success": False}
    
    async def _execute_cad_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute CAD/3D printing/laser engraving task."""
        op = task.operation
        logger.info(f"🔧 CAD task: {op}")
        
        if op == "generate_cad":
            model = await engine.generate_from_text(
                task.params.get('description', ''),
                optimization_objective=None
            )
            return {"type": "cad_model", "model_id": model.id}
        
        elif op == "generate_cad_from_image":
            image_path = ""
            if isinstance(input_data, dict):
                image_path = str(
                    input_data.get("path")
                    or input_data.get("image_path")
                    or input_data.get("file_path")
                    or ""
                )
            if not image_path:
                # No source image available; fall back to text CAD.
                model = await engine.generate_from_text(task.params.get('description', ''), optimization_objective=None)
                return {"type": "cad_model", "model_id": model.id, "source": "text_fallback"}
            model = await engine.generate_from_image(image_path, maintain_dimensions=True)
            return {"type": "cad_model", "model_id": model.id, "source_image": image_path}
        
        elif op == "export_stl":
            model_id = task.params.get('model_id', '') or (input_data or {}).get('model_id', '')
            path = engine.export_stl(model_id)
            return {"type": "stl_file", "path": path}
        
        elif op == "generate_gcode":
            model_id = task.params.get('model_id', '') or (input_data or {}).get('model_id', '')
            program = engine.generate_gcode_fdm(model_id)
            return {"type": "gcode", "layers": program.layer_count}
        
        elif op == "laser_engrave":
            program = engine.generate_gcode_laser(
                source_file=task.params.get('source_file', ''),
                power_percent=task.params.get('power', 80),
                speed_mm_min=task.params.get('speed', 1000),
            )
            return {"type": "laser_gcode", "commands": len(program.commands)}
        
        elif op == "search_stl":
            results = await engine.search_stl_models(
                task.params.get('query', ''),
                source=task.params.get('source', 'thingiverse'),
            )
            return {"type": "stl_search", "results": len(results)}
        
        elif op == "analyze_stl":
            analysis = engine.analyze_stl(task.params.get('stl_path', ''))
            return {"type": "stl_analysis", "data": analysis}
        
        elif op == "generate_blueprint":
            model_id = (input_data or {}).get('model_id', '')
            description = task.params.get('description', '')
            if not model_id and hasattr(engine, '_models') and engine._models:
                model_id = list(engine._models.keys())[-1]
            hierarchy = {}
            if model_id and hasattr(engine, '_models') and model_id in engine._models:
                model = engine._models[model_id]
                hierarchy = (model.metadata or {}).get('object_hierarchy', {}) or {}
            if not hierarchy and description:
                hierarchy = await engine._decompose_object(description)
            from pathlib import Path
            out_dir = Path(__file__).parent.parent / "exports" / "blueprints"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = str(out_dir / f"blueprint_{int(time.time() * 1000)}.dxf")
            path = engine.generate_blueprint_dxf(hierarchy, out_path, title=description[:60] or "Assembly Blueprint")
            return {"type": "blueprint", "path": path, "format": "dxf"} if path else {"type": "blueprint", "error": "generation failed"}
        
        elif op == "generate_schematic":
            model_id = (input_data or {}).get('model_id', '')
            description = task.params.get('description', '')
            if not model_id and hasattr(engine, '_models') and engine._models:
                model_id = list(engine._models.keys())[-1]
            hierarchy = {}
            if model_id and hasattr(engine, '_models') and model_id in engine._models:
                model = engine._models[model_id]
                hierarchy = (model.metadata or {}).get('object_hierarchy', {}) or {}
            if not hierarchy and description:
                hierarchy = await engine._decompose_object(description)
            from pathlib import Path
            out_dir = Path(__file__).parent.parent / "exports" / "schematics"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = str(out_dir / f"schematic_{int(time.time() * 1000)}.svg")
            path = engine.generate_schematic_svg(hierarchy, out_path, title=description[:60] or "Assembly Schematic")
            return {"type": "schematic", "path": path, "format": "svg"} if path else {"type": "schematic", "error": "generation failed"}
        
        return {"type": "cad", "operation": op}

    async def _execute_booktok_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute BookTok explainability/storyboard tasks."""
        op = task.operation
        logger.info(f"📚 BookTok task: {op}")
        prompt = str(task.params.get("prompt", ""))
        if isinstance(input_data, dict):
            prompt = prompt or str(
                input_data.get("prompt")
                or input_data.get("description")
                or input_data.get("path")
                or input_data.get("model_id")
                or ""
            )

        if op == "explain_mechanics":
            try:
                if hasattr(engine, "create_booktok_context"):
                    context, storyboard = await engine.create_booktok_context(
                        f"Explain how this engineered object works in detail for users: {prompt}"
                    )
                    result = {
                        "type": "booktok_explainer",
                        "context": context,
                        "storyboard": storyboard,
                        "prompt": prompt,
                    }
                    if self.event_bus:
                        self.event_bus.publish("booktok.explainer.generated", result)
                    return result
            except Exception as e:
                logger.warning(f"BookTok explain_mechanics fallback: {e}")
            return {
                "type": "booktok_explainer",
                "prompt": prompt,
                "summary": f"Engineering breakdown generated for: {prompt[:120]}",
            }

        if op == "generate_storyboard":
            try:
                context = {}
                if isinstance(input_data, dict):
                    context = input_data.get("context", {}) or {}
                if hasattr(engine, "generate_storyboard"):
                    storyboard = await engine.generate_storyboard(prompt, context)
                    return {"type": "booktok_storyboard", "storyboard": storyboard, "prompt": prompt}
            except Exception as e:
                logger.warning(f"BookTok generate_storyboard fallback: {e}")
            return {"type": "booktok_storyboard", "prompt": prompt, "status": "fallback"}

        return {"type": "booktok", "operation": op, "prompt": prompt}

    async def _execute_technical_viz_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute technical visualization tasks with proper render contract."""
        op = task.operation
        logger.info(f"📐 Technical viz task: {op}")

        if op != "render":
            # Fall back to generic behavior for non-render operations.
            if hasattr(engine, op):
                method = getattr(engine, op)
                if asyncio.iscoroutinefunction(method):
                    return await method(**task.params)
                return method(**task.params)
            return {"type": "technical_viz", "operation": op}

        # render() requires (prompt, TechnicalConfig); orchestrator previously
        # called it with only keyword params which caused hard pipeline failure.
        from gui.widgets.technical_visualization_engine import TechnicalConfig, TechnicalMode

        prompt = task.params.get("prompt", "")
        if not prompt and isinstance(input_data, dict):
            prompt = str(
                input_data.get("description")
                or input_data.get("path")
                or input_data.get("model_id")
                or "engineering exploded assembly"
            )
        if not prompt:
            prompt = "engineering exploded assembly"

        mode_str = str(task.params.get("mode", "mathematics"))
        # Map custom orchestrator modes to existing technical engine enum.
        mode_aliases = {
            "engineering_exploded": "geometry",
            "physics": "geometry",
            "schematic": "geometry",
        }
        mode_value = mode_aliases.get(mode_str.lower(), mode_str.lower())
        try:
            mode = TechnicalMode(mode_value)
        except Exception:
            mode = TechnicalMode.GEOMETRY

        config = TechnicalConfig(
            mode=mode,
            width=int(task.params.get("width", 1024)),
            height=int(task.params.get("height", 576)),
            detail_level=int(task.params.get("detail_level", 3)),
            show_grid=bool(task.params.get("show_grid", True)),
            show_labels=bool(task.params.get("show_labels", True)),
            show_axes=bool(task.params.get("show_axes", True)),
            color_scheme=str(task.params.get("color_scheme", "blueprint")),
        )

        image = engine.render(prompt, config)
        out_dir = Path("exports") / "creations"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"technical_viz_{int(time.time() * 1000)}.png"
        image.save(str(out_path))

        return {
            "type": "technical_visual",
            "path": str(out_path),
            "prompt": prompt,
            "mode": mode.value,
        }
    
    async def _execute_electronics_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute electronics/PCB task."""
        op = task.operation
        logger.info(f"⚡ Electronics task: {op}")
        
        if op == "generate_circuit":
            circuit = await engine.generate_circuit(
                task.params.get('description', ''),
                optimize_for=task.params.get('optimize_for', 'size'),
            )
            return {"type": "circuit", "circuit_id": circuit.id}
        
        elif op == "generate_gerber":
            circuit_id = task.params.get('circuit_id', '') or (input_data or {}).get('circuit_id', '')
            files = engine.generate_gerber_files(circuit_id)
            return {"type": "gerber_files", "files": list(files.keys())}
        
        elif op == "get_manufacturing_quotes":
            circuit_id = task.params.get('circuit_id', '') or (input_data or {}).get('circuit_id', '')
            quotes = await engine.get_all_manufacturing_quotes(circuit_id)
            return {"type": "quotes", "count": len(quotes)}
        
        elif op == "prepare_desktop_print":
            circuit_id = task.params.get('circuit_id', '') or (input_data or {}).get('circuit_id', '')
            result = await engine.prepare_desktop_print(circuit_id)
            return {"type": "pcb_print_ready", "data": result}
        
        elif op == "export_kicad":
            circuit_id = task.params.get('circuit_id', '') or (input_data or {}).get('circuit_id', '')
            files = engine.generate_kicad_project(circuit_id)
            return {"type": "kicad_project", "files": list(files.keys())}
        
        return {"type": "electronics", "operation": op}
    
    async def _execute_industrial_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute industrial product design task."""
        op = task.operation
        logger.info(f"🏭 Industrial task: {op}")
        
        if op == "generate_product":
            from core.industrial_product_design_engine import ProductCategory, DesignStyle
            design = await engine.generate_product(
                task.params.get('description', ''),
                category=ProductCategory(task.params.get('category', 'consumer_electronics')),
                style=DesignStyle(task.params.get('style', 'minimalist')),
            )
            return {"type": "product_design", "design_id": design.id}
        
        elif op == "recommend_material":
            mat = engine.recommend_material(task.params.get('description', ''))
            return {"type": "material", "name": mat.name if mat else "Unknown"}
        
        elif op == "search_materials":
            results = engine.search_materials(
                min_tensile_mpa=task.params.get('min_tensile', 0),
                needs_metal=task.params.get('metal', False),
                needs_flexible=task.params.get('flexible', False),
            )
            return {"type": "materials", "count": len(results)}
        
        return {"type": "industrial", "operation": op}
    
    async def _execute_generic_task(self, engine, task: EngineTask, input_data: Any) -> Any:
        """Execute a generic engine task by calling common methods."""
        logger.info(f"🔄 Generic task: {task.engine.value} - {task.operation}")
        
        op = task.operation
        if hasattr(engine, op):
            method = getattr(engine, op)
            if asyncio.iscoroutinefunction(method):
                return await method(**task.params)
            else:
                return method(**task.params)
        
        return {"type": task.engine.value, "operation": op, "status": "executed"}
    
    async def _execute_hybrid(self, pipeline: CreationPipeline, outputs: Dict[str, Any]) -> Any:
        """Execute hybrid workflow with custom dependency resolution."""
        # Build dependency graph
        task_map = {task.output_key: task for task in pipeline.tasks}
        executed = set()
        
        async def execute_with_deps(task: EngineTask):
            # Execute dependencies first
            if task.input_from and task.input_from not in executed:
                dep_task = task_map.get(task.input_from)
                if dep_task:
                    await execute_with_deps(dep_task)
            
            # Execute this task
            if task.output_key not in executed:
                result = await self._execute_task(task, outputs)
                outputs[task.output_key] = result
                executed.add(task.output_key)
                return result
        
        # Execute all tasks with dependency resolution
        for task in pipeline.tasks:
            await execute_with_deps(task)
        
        # Return last task output
        return outputs.get(pipeline.tasks[-1].output_key)
    
    def _composite_layers(self, layers: List[Any]) -> Any:
        """Composite multiple layers into final output.
        
        Currently returns the topmost layer. Full image-stacking / video-overlay
        compositing requires a dedicated rendering backend (e.g. Pillow or FFmpeg)
        and will be wired in when those engines are available.
        """
        logger.info(f"🎨 Compositing {len(layers)} layers (returning top layer)")
        return layers[-1]
    
    def parse_request(self, request: str) -> CreationPipeline:
        """
        Parse natural language request into multi-engine pipeline.
        
        Examples:
        - "Create a holographic medical heart animation"
        - "Generate a fantasy world map with animated clouds"
        - "Create a cyberpunk city schematic"
        """
        pipeline_id = f"pipeline_{int(time.time() * 1000)}"
        tasks = []
        
        # SOTA 2026 whole-studio policy planner (primary path).
        policy_pipeline = self._build_whole_studio_chain(request)
        if policy_pipeline and policy_pipeline.tasks:
            logger.info(
                "🧠 Whole-studio routing selected %d engines: %s",
                len(policy_pipeline.tasks),
                [t.engine.value for t in policy_pipeline.tasks],
            )
            return policy_pipeline
        
        # Keyword-based fallback routing (whole-studio policy planner above is the primary path)
        request_lower = request.lower()
        
        # Medical + Animation + Video
        if 'medical' in request_lower and 'animation' in request_lower:
            tasks.extend([
                EngineTask(
                    engine=EngineType.MEDICAL,
                    operation="reconstruct_3d",
                    params={"prompt": request},
                    output_key="medical_model"
                ),
                EngineTask(
                    engine=EngineType.ANIMATION,
                    operation="animate",
                    params={"effect": "holographic", "frames": 120},
                    input_from="medical_model",
                    output_key="animated_model"
                ),
                EngineTask(
                    engine=EngineType.CINEMA,
                    operation="render_video",
                    params={"quality": "high", "fps": 30},
                    input_from="animated_model",
                    output_key="final"
                )
            ])
            mode = CompositionMode.SEQUENTIAL
        
        # Map + Animation + Video
        elif 'map' in request_lower and ('animated' in request_lower or 'animation' in request_lower):
            tasks.extend([
                EngineTask(
                    engine=EngineType.CREATIVE,
                    operation="generate_map",
                    params={"prompt": request, "map_type": "world"},
                    output_key="map"
                ),
                EngineTask(
                    engine=EngineType.ANIMATION,
                    operation="add_particles",
                    params={"particle_type": "clouds", "frames": 240},
                    input_from="map",
                    output_key="animated_map"
                ),
                EngineTask(
                    engine=EngineType.CINEMA,
                    operation="render_flythrough",
                    params={"duration": 10, "fps": 24},
                    input_from="animated_map",
                    output_key="final"
                )
            ])
            mode = CompositionMode.SEQUENTIAL
        
        # Schematic/Blueprint + Visual Enhancement
        elif 'schematic' in request_lower or 'blueprint' in request_lower:
            tasks.extend([
                EngineTask(
                    engine=EngineType.CREATIVE,
                    operation="generate_schematic",
                    params={"prompt": request, "style": "technical"},
                    output_key="schematic"
                ),
                EngineTask(
                    engine=EngineType.VISUAL,
                    operation="enhance_image",
                    params={"prompt": request, "style": "detailed"},
                    input_from="schematic",
                    output_key="final"
                )
            ])
            mode = CompositionMode.SEQUENTIAL
        
        # SOTA 2026: STORY/MOVIE/GAME GENERATION
        # ========================================
        
        # Full Movie/Short: Screenplay → Storyboard → Characters → Video
        elif any(keyword in request_lower for keyword in ['movie', 'short', 'film', 'feature']):
            tasks.extend([
                EngineTask(
                    engine=EngineType.SCREENPLAY,
                    operation="generate_screenplay",
                    params={"premise": request, "genre": "auto", "num_scenes": 10},
                    output_key="screenplay"
                ),
                EngineTask(
                    engine=EngineType.CHARACTER_CONSISTENCY,
                    operation="generate_character_sheets",
                    params={"screenplay": None},  # Will use screenplay from input
                    input_from="screenplay",
                    output_key="characters"
                ),
                EngineTask(
                    engine=EngineType.STORYBOARD,
                    operation="plan_storyboard",
                    params={"screenplay": None, "style": "cinematic"},
                    input_from="screenplay",
                    output_key="storyboard"
                ),
                EngineTask(
                    engine=EngineType.CINEMA,
                    operation="render_multi_shot_video",
                    params={"storyboard": None, "characters": None},
                    input_from="storyboard",
                    output_key="final"
                )
            ])
            mode = CompositionMode.SEQUENTIAL
        
        # Story/Narrative: Screenplay only (text output)
        elif any(keyword in request_lower for keyword in ['story', 'narrative', 'screenplay', 'script', 'tale']):
            tasks.append(
                EngineTask(
                    engine=EngineType.SCREENPLAY,
                    operation="generate_screenplay",
                    params={"premise": request, "genre": "auto", "num_scenes": 15},
                    output_key="final"
                )
            )
            mode = CompositionMode.SEQUENTIAL
        
        # Game/World: World Generation → Unity Export
        elif any(keyword in request_lower for keyword in ['game', 'world', 'level', 'dungeon', 'arena']):
            tasks.extend([
                EngineTask(
                    engine=EngineType.WORLD_GEN,
                    operation="generate_world",
                    params={"description": request, "scale": "auto", "type": "auto"},
                    output_key="world"
                ),
                EngineTask(
                    engine=EngineType.UNITY,
                    operation="export_to_unity",
                    params={"world": None},
                    input_from="world",
                    output_key="final"
                )
            ])
            mode = CompositionMode.SEQUENTIAL
        
        # Storyboard/Animatic: Storyboard → Animatic Video
        elif any(keyword in request_lower for keyword in ['storyboard', 'animatic', 'previz']):
            tasks.extend([
                EngineTask(
                    engine=EngineType.STORYBOARD,
                    operation="plan_from_description",
                    params={"description": request, "num_shots": 12},
                    output_key="storyboard"
                ),
                EngineTask(
                    engine=EngineType.STORYBOARD,
                    operation="generate_animatic",
                    params={"storyboard": None},
                    input_from="storyboard",
                    output_key="final"
                )
            ])
            mode = CompositionMode.SEQUENTIAL
        
        # SOTA 2026: DESIGN/ENGINEERING GENERATION
        # ==========================================
        
        # Engineering exploded assembly chain:
        # CAD model -> STL artifact -> technical viz -> animation -> cinema render.
        elif any(keyword in request_lower for keyword in ['exploded', 'disassembled', 'assembly', 'parts assembling']) and any(
            keyword in request_lower for keyword in ['cad', 'mechanical', 'engineering', 'car', 'supercar', 'engine', 'component']
        ):
            tasks.extend([
                EngineTask(
                    engine=EngineType.CAD_MECHANICAL,
                    operation="generate_cad",
                    params={"description": request, "optimization_objective": "auto"},
                    output_key="cad_model"
                ),
                EngineTask(
                    engine=EngineType.CAD_MECHANICAL,
                    operation="export_stl",
                    params={},
                    input_from="cad_model",
                    output_key="stl_file"
                ),
                EngineTask(
                    engine=EngineType.TECHNICAL_VIZ,
                    operation="render",
                    params={"mode": "engineering_exploded"},
                    input_from="stl_file",
                    output_key="technical_visual"
                ),
                EngineTask(
                    engine=EngineType.ANIMATION,
                    operation="animate",
                    params={"style": "exploded_assembly", "frames": 180, "fps": 30},
                    input_from="technical_visual",
                    output_key="animated_sequence"
                ),
                EngineTask(
                    engine=EngineType.CINEMA,
                    operation="render_video",
                    params={"quality": "high", "fps": 30},
                    input_from="animated_sequence",
                    output_key="final"
                ),
            ])
            mode = CompositionMode.SEQUENTIAL

        # CAD/Mechanical: CAD model with optimization
        elif any(keyword in request_lower for keyword in ['cad', 'mechanical', 'engineering', 'machine part', 'component']):
            tasks.append(
                EngineTask(
                    engine=EngineType.CAD_MECHANICAL,
                    operation="generate_cad",
                    params={"description": request, "optimization_objective": "auto"},
                    output_key="final"
                )
            )
            mode = CompositionMode.SEQUENTIAL
        
        # Fashion/Clothing: Pattern + 3D garment + virtual try-on
        elif any(keyword in request_lower for keyword in ['fashion', 'clothing', 'garment', 'dress', 'shirt', 'pants']):
            tasks.extend([
                EngineTask(
                    engine=EngineType.FASHION_CLOTHING,
                    operation="generate_pattern",
                    params={"description": request, "garment_type": "auto"},
                    output_key="pattern"
                ),
                EngineTask(
                    engine=EngineType.FASHION_CLOTHING,
                    operation="generate_3d_garment",
                    params={"description": request},
                    output_key="final"
                )
            ])
            mode = CompositionMode.SEQUENTIAL
        
        # Architecture/Building: Floor plan + building model
        elif any(keyword in request_lower for keyword in ['architecture', 'building', 'floor plan', 'house', 'office']):
            tasks.append(
                EngineTask(
                    engine=EngineType.ARCHITECTURAL,
                    operation="generate_floor_plan",
                    params={"requirements": request, "building_type": "auto"},
                    output_key="final"
                )
            )
            mode = CompositionMode.SEQUENTIAL
        
        # Electronics/Circuit: Circuit design + PCB layout
        elif any(keyword in request_lower for keyword in ['circuit', 'pcb', 'electronics', 'microcontroller', 'arduino']):
            tasks.append(
                EngineTask(
                    engine=EngineType.ELECTRONICS_CIRCUIT,
                    operation="generate_circuit",
                    params={"description": request, "optimize_for": "size"},
                    output_key="final"
                )
            )
            mode = CompositionMode.SEQUENTIAL
        
        # Industrial/Product: Product design + PBR textures
        elif any(keyword in request_lower for keyword in ['product', 'industrial design', 'consumer product', 'gadget']):
            tasks.append(
                EngineTask(
                    engine=EngineType.INDUSTRIAL_PRODUCT,
                    operation="generate_product",
                    params={"description": request, "category": "auto", "style": "minimalist"},
                    output_key="final"
                )
            )
            mode = CompositionMode.SEQUENTIAL

        # Physics + engineering chain:
        # design artifact -> technical analysis -> motion visualization -> video render.
        elif any(keyword in request_lower for keyword in [
            'physics', 'simulation', 'cfd', 'wind tunnel', 'turbulence', 'buoyancy',
            'water surface', 'structural', 'stress', 'strain', 'chemistry', 'thermal',
            'metallurgy', 'alloy', 'reactor'
        ]):
            tasks.extend([
                EngineTask(
                    engine=EngineType.CREATIVE,
                    operation="generate_schematic",
                    params={"prompt": request, "style": "engineering"},
                    output_key="engineering_spec"
                ),
                EngineTask(
                    engine=EngineType.TECHNICAL_VIZ,
                    operation="render",
                    params={"spec": None, "domain": "multiphysics"},
                    input_from="engineering_spec",
                    output_key="physics_visual"
                ),
                EngineTask(
                    engine=EngineType.ANIMATION,
                    operation="animate",
                    params={"frames": 180, "fps": 30, "style": "simulation"},
                    input_from="physics_visual",
                    output_key="animated_simulation"
                ),
                EngineTask(
                    engine=EngineType.CINEMA,
                    operation="render_video",
                    params={"quality": "high", "fps": 30},
                    input_from="animated_simulation",
                    output_key="final"
                )
            ])
            mode = CompositionMode.SEQUENTIAL
        
        # Default: COLLECTIVE - Creative + Visual (every engine contributes)
        # Creative establishes domain/style; Visual generates image. Maps go through Creative first.
        else:
            wants_map = any(k in request_lower for k in ['map', 'world', 'terrain', 'dungeon', 'city', 'kingdom'])
            if wants_map:
                tasks.extend([
                    EngineTask(EngineType.CREATIVE, "create", params={"prompt": request}, output_key="creative_spec"),
                    EngineTask(EngineType.VISUAL, "generate_image", params={"prompt": request}, input_from="creative_spec", output_key="final"),
                ])
            else:
                tasks.extend([
                    EngineTask(EngineType.CREATIVE, "create", params={"prompt": request}, output_key="creative_spec"),
                    EngineTask(EngineType.VISUAL, "generate_image", params={"prompt": request}, input_from="creative_spec", output_key="final"),
                ])
            mode = CompositionMode.SEQUENTIAL
        
        return CreationPipeline(
            id=pipeline_id,
            description=request,
            tasks=tasks,
            mode=mode,
            metadata={"original_request": request}
        )


# Global singleton
_orchestrator = None


def get_orchestrator(event_bus=None) -> CreationOrchestrator:
    """Get or create global orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CreationOrchestrator(event_bus=event_bus)
    return _orchestrator
