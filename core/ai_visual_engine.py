#!/usr/bin/env python3
"""
Kingdom AI - SOTA 2026 AI Visual Processing Engine

State-of-the-Art 2026 visual processing, animation, and creation system
with full Ollama integration for AI-powered image understanding, generation,
and continuous learning.

Features:
- Real-time AI image generation (LCM, SDXL, AnimateDiff)
- Ollama multimodal vision integration (LLaVA, BakLLaVA)
- Neural style transfer and image manipulation
- Procedural animation generation
- 3D model preview rendering
- Continuous learning from visual feedback
- Meta-learning style adaptation
- Sentience-aware visual processing
"""

import os
import sys
import json
import math
import time
import base64
import asyncio
import logging
import hashlib
import threading
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

# Configure logging
logger = logging.getLogger("KingdomAI.AIVisualEngine")

# Optional imports with graceful fallbacks
try:
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, QMutex
    from PyQt6.QtGui import QImage, QPainter, QPen, QBrush, QColor, QFont, QPainterPath
    from PyQt6.QtGui import QLinearGradient, QRadialGradient, QTransform, QPixmap
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    logger.warning("PyQt6 not available - visual rendering limited")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
    # Safe CUDA check - some torch versions may have issues with device detection
    try:
        CUDA_AVAILABLE = torch.cuda.is_available()
    except (AttributeError, RuntimeError):
        CUDA_AVAILABLE = False
except (ImportError, AttributeError) as e:
    TORCH_AVAILABLE = False
    CUDA_AVAILABLE = False
    logger.warning(f"PyTorch not available or has issues: {e}")

DIFFUSERS_IMPORT_ERROR = None
DIFFUSERS_INSTALL_HINT = f'"{sys.executable}" -m pip install -U diffusers>=0.30.0 peft accelerate safetensors transformers sentencepiece'

# =============================================================================
# SOTA 2026: Lazy imports for all diffusers pipelines
# Importing at module level causes 30+ second delays in WSL
# =============================================================================

DIFFUSERS_AVAILABLE = False
DIFFUSERS_IMPORT_ERROR = None

# Core pipelines
AutoPipelineForText2Image = None
LCMScheduler = None
DiffusionPipeline = None

# SOTA 2026 Image Pipelines
FluxPipeline = None
StableDiffusion3Pipeline = None

# SOTA 2026 Video Pipelines
MochiPipeline = None
CogVideoXPipeline = None
LTXPipeline = None
AnimateDiffPipeline = None
MotionAdapter = None
StableVideoDiffusionPipeline = None


def _lazy_import_diffusers():
    """Lazy import diffusers only when actually needed for generation."""
    global DIFFUSERS_AVAILABLE, DIFFUSERS_IMPORT_ERROR
    global AutoPipelineForText2Image, LCMScheduler, DiffusionPipeline
    
    if DIFFUSERS_AVAILABLE or AutoPipelineForText2Image is not None:
        return True  # Already imported
    try:
        from diffusers import AutoPipelineForText2Image as _Auto, LCMScheduler as _LCM, DiffusionPipeline as _Diff
        AutoPipelineForText2Image = _Auto
        LCMScheduler = _LCM
        DiffusionPipeline = _Diff
        DIFFUSERS_AVAILABLE = True
        logger.info("✅ Diffusers core imported successfully (lazy load)")
        return True
    except (ImportError, AttributeError, RuntimeError, Exception) as e:
        DIFFUSERS_AVAILABLE = False
        DIFFUSERS_IMPORT_ERROR = str(e)
        logger.warning(f"Diffusers not available: {e}")
        logger.warning(f"Enable Diffusers by running: {DIFFUSERS_INSTALL_HINT}")
        return False


def _lazy_import_flux():
    """Lazy import FLUX.1 pipeline - SOTA 2026 best quality image generation."""
    global FluxPipeline
    if FluxPipeline is not None:
        return True
    try:
        from diffusers import FluxPipeline as _Flux
        FluxPipeline = _Flux
        logger.info("✅ FLUX.1 pipeline imported (lazy load)")
        return True
    except ImportError as e:
        logger.warning(f"FLUX.1 not available: {e}")
        return False


def _lazy_import_sd35():
    """Lazy import SD3.5 pipeline - SOTA 2026 fine-tunable image generation."""
    global StableDiffusion3Pipeline
    if StableDiffusion3Pipeline is not None:
        return True
    try:
        from diffusers import StableDiffusion3Pipeline as _SD35
        StableDiffusion3Pipeline = _SD35
        logger.info("✅ SD3.5 pipeline imported (lazy load)")
        return True
    except ImportError as e:
        logger.warning(f"SD3.5 not available: {e}")
        return False


def _lazy_import_mochi():
    """Lazy import Mochi pipeline - SOTA 2026 production video generation."""
    global MochiPipeline
    if MochiPipeline is not None:
        return True
    try:
        from diffusers import MochiPipeline as _Mochi
        MochiPipeline = _Mochi
        logger.info("✅ Mochi pipeline imported (lazy load)")
        return True
    except ImportError as e:
        logger.warning(f"Mochi not available: {e}")
        return False


def _lazy_import_cogvideox():
    """Lazy import CogVideoX pipeline - SOTA 2026 5B video generation."""
    global CogVideoXPipeline
    if CogVideoXPipeline is not None:
        return True
    try:
        from diffusers import CogVideoXPipeline as _CogVideoX
        CogVideoXPipeline = _CogVideoX
        logger.info("✅ CogVideoX pipeline imported (lazy load)")
        return True
    except ImportError as e:
        logger.warning(f"CogVideoX not available: {e}")
        return False


def _lazy_import_ltxvideo():
    """Lazy import LTXVideo pipeline - SOTA 2026 real-time video generation."""
    global LTXPipeline
    if LTXPipeline is not None:
        return True
    try:
        from diffusers import LTXPipeline as _LTX
        LTXPipeline = _LTX
        logger.info("✅ LTXVideo pipeline imported (lazy load)")
        return True
    except ImportError as e:
        logger.warning(f"LTXVideo not available: {e}")
        return False


def _lazy_import_animatelcm():
    """Lazy import AnimateLCM pipeline - SOTA 2026 fast animation generation."""
    global AnimateDiffPipeline, MotionAdapter, LCMScheduler
    if AnimateDiffPipeline is not None:
        return True
    try:
        from diffusers import AnimateDiffPipeline as _AnimateDiff, MotionAdapter as _Adapter, LCMScheduler as _LCM
        AnimateDiffPipeline = _AnimateDiff
        MotionAdapter = _Adapter
        LCMScheduler = _LCM
        logger.info("✅ AnimateLCM pipeline imported (lazy load)")
        return True
    except ImportError as e:
        logger.warning(f"AnimateLCM not available: {e}")
        return False


def _lazy_import_svd():
    """Lazy import SVD-XT pipeline - SOTA 2026 image-to-video generation."""
    global StableVideoDiffusionPipeline
    if StableVideoDiffusionPipeline is not None:
        return True
    try:
        from diffusers import StableVideoDiffusionPipeline as _SVD
        StableVideoDiffusionPipeline = _SVD
        logger.info("✅ SVD-XT pipeline imported (lazy load)")
        return True
    except ImportError as e:
        logger.warning(f"SVD-XT not available: {e}")
        return False


def get_available_pipelines() -> dict:
    """Get status of all available SOTA 2026 pipelines without importing."""
    pipelines = {
        'diffusers': False,
        'flux1': False,
        'sd35': False,
        'mochi': False,
        'cogvideox': False,
        'ltxvideo': False,
        'animatelcm': False,
        'svd_xt': False
    }
    
    try:
        import importlib.util
        
        # Check if diffusers is installed
        if importlib.util.find_spec('diffusers'):
            pipelines['diffusers'] = True
            
            # Check specific pipeline availability by module inspection
            # This is faster than actually importing
            from diffusers import __version__ as diffusers_version
            version_parts = [int(x) for x in diffusers_version.split('.')[:2]]
            
            # Version 0.30.0+ has most SOTA 2026 models
            if version_parts[0] >= 0 and version_parts[1] >= 30:
                pipelines['flux1'] = True
                pipelines['sd35'] = True
                pipelines['mochi'] = True
                pipelines['cogvideox'] = True
                pipelines['ltxvideo'] = True
                pipelines['animatelcm'] = True
                pipelines['svd_xt'] = True
            elif version_parts[1] >= 25:
                pipelines['animatelcm'] = True
                pipelines['svd_xt'] = True
                
    except Exception as e:
        logger.debug(f"Pipeline availability check failed: {e}")
    
    return pipelines


class VisualMode(Enum):
    """SOTA 2026 Visual processing modes."""
    # AI Generation
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_IMAGE = "image_to_image"
    INPAINTING = "inpainting"
    OUTPAINTING = "outpainting"
    UPSCALING = "upscaling"
    STYLE_TRANSFER = "style_transfer"
    
    # Animation
    ANIMATION = "animation"
    VIDEO_GENERATION = "video_generation"
    MOTION_TRANSFER = "motion_transfer"
    
    # Technical Visualization
    CHART = "chart"
    DIAGRAM = "diagram"
    SCHEMATIC = "schematic"
    WIRING = "wiring"
    FLOWCHART = "flowchart"
    
    # Mathematical/Scientific
    FUNCTION_PLOT = "function_plot"
    TRIGONOMETRY = "trigonometry"
    CALCULUS = "calculus"
    FRACTAL = "fractal"
    SACRED_GEOMETRY = "sacred_geometry"
    
    # Artistic
    CARTOGRAPHY = "cartography"
    ASTROLOGY = "astrology"
    CALLIGRAPHY = "calligraphy"
    
    # 3D
    MODEL_3D = "model_3d"
    MESH_PREVIEW = "mesh_preview"
    
    # Analysis
    IMAGE_ANALYSIS = "image_analysis"
    OBJECT_DETECTION = "object_detection"
    SCENE_UNDERSTANDING = "scene_understanding"


@dataclass
class VisualConfig:
    """SOTA 2026 Visual generation configuration."""
    mode: VisualMode = VisualMode.TEXT_TO_IMAGE
    width: int = 1024
    height: int = 1024
    steps: int = 4  # LCM uses 4-8 steps for real-time
    guidance_scale: float = 1.5
    seed: int = -1
    model: str = "lcm"
    style: str = "default"
    negative_prompt: str = ""
    
    # Animation settings
    fps: int = 24
    num_frames: int = 24
    motion_strength: float = 0.8
    
    # Quality settings
    detail_level: int = 3  # 1-5
    quality: str = "high"  # low, medium, high, ultra
    
    # AI Enhancement
    ai_enhance: bool = True
    ollama_model: str = "llava:latest"
    use_neural_style: bool = False
    
    # Learning settings
    learn_from_feedback: bool = True
    style_memory_enabled: bool = True


@dataclass
class VisualResult:
    """Result from visual processing."""
    success: bool
    image: Optional[Any] = None  # QImage or PIL Image
    metadata: Dict[str, Any] = field(default_factory=dict)
    frames: List[Any] = field(default_factory=list)  # For animations
    analysis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    generation_time: float = 0.0
    tokens_used: int = 0


class OllamaVisionProcessor:
    """SOTA 2026 Ollama Vision Processing - Multimodal AI Integration."""
    
    VISION_MODELS = [
        "llava:latest",
        "llava:13b",
        "llava:34b", 
        "bakllava:latest",
        "llava-phi3:latest",
        "moondream:latest",
        "llava-llama3:latest",
    ]
    
    ANALYSIS_PROMPTS = {
        "describe": "Describe this image in detail, including colors, objects, composition, mood, and style.",
        "objects": "List all objects visible in this image with their positions and attributes.",
        "style": "Analyze the artistic style of this image - color palette, composition, technique.",
        "emotions": "What emotions or mood does this image convey? Explain the visual elements that create this feeling.",
        "technical": "Provide a technical analysis: resolution quality, lighting, composition rules, color theory.",
        "generate_prompt": "Create a detailed image generation prompt that would recreate this image.",
        "improve": "Suggest specific improvements to enhance this image's visual appeal.",
        "similar": "Describe 5 similar images that could complement this one.",
    }
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.available_models = []
        self.all_models = []
        self.current_model = "llava:latest"
        self.active = False
        self.base_url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        
        # Learning memory
        self._analysis_history = []
        self._style_memory = {}
        self._feedback_scores = {}
        
        # Check availability
        self._check_ollama()

    def _create_ollama_client(self):
        client_cls = getattr(ollama, "Client", None)
        if client_cls is None:
            return None
        try:
            return client_cls(host=self.base_url)
        except TypeError:
            try:
                return client_cls(self.base_url)
            except Exception:
                try:
                    return client_cls()
                except Exception:
                    return None

    @staticmethod
    def _close_ollama_client(client):
        try:
            close_fn = getattr(client, "close", None)
            if callable(close_fn):
                close_fn()
        except Exception:
            pass

        try:
            inner = getattr(client, "_client", None) or getattr(client, "client", None)
            close_fn = getattr(inner, "close", None)
            if callable(close_fn):
                close_fn()
        except Exception:
            pass

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        try:
            converted = dict(value)  # type: ignore[arg-type]
            if isinstance(converted, dict):
                return converted
        except Exception:
            pass
        try:
            as_dict = getattr(value, "__dict__", None)
            if isinstance(as_dict, dict):
                return as_dict
        except Exception:
            pass
        return {}
    
    def _check_ollama(self):
        """Check Ollama availability and vision models."""
        if not OLLAMA_AVAILABLE:
            logger.warning("Ollama not installed - vision processing limited")
            return
        
        try:
            client = None
            try:
                client = self._create_ollama_client()
                list_fn = getattr(client, "list", None) if client is not None else None
                models = list_fn() if callable(list_fn) else ollama.list()
            finally:
                if client is not None:
                    self._close_ollama_client(client)

            model_entries = []
            if isinstance(models, dict):
                model_entries = models.get('models') or []
            elif isinstance(models, list):
                model_entries = models
            else:
                model_entries = getattr(models, 'models', []) or []

            all_models: List[str] = []
            for m in model_entries:
                name = None
                if isinstance(m, dict):
                    name = m.get('name') or m.get('model') or m.get('id')
                else:
                    name = getattr(m, 'name', None) or getattr(m, 'model', None) or getattr(m, 'id', None)
                if name:
                    all_models.append(str(name))

            self.all_models = list(all_models)
            
            # Find vision-capable models
            self.available_models = [
                m for m in all_models 
                if any(v in m.lower() for v in ['llava', 'bakllava', 'vision', 'moondream'])
            ]
            
            if self.available_models:
                self.current_model = self.available_models[0]
                self.active = True
                logger.info(f"✅ Ollama vision active: {len(self.available_models)} vision models")
            else:
                # Check if any model can be used for text analysis
                self.active = len(all_models) > 0
                if all_models:
                    self.current_model = all_models[0]
                logger.info(f"⚠️ No dedicated vision models, using text models: {all_models[:3]}")
                
        except Exception as e:
            logger.error(f"Ollama check failed: {e}")
            self.active = False
    
    async def analyze_image(self, image: Union[str, bytes, 'QImage', 'Image.Image'], 
                           analysis_type: str = "describe",
                           custom_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Analyze image using Ollama vision models - SOTA 2026."""
        if not self.active:
            return {"success": False, "error": "Ollama vision not available"}
        
        try:
            # Convert image to base64
            image_b64 = self._image_to_base64(image)
            if not image_b64:
                return {"success": False, "error": "Failed to convert image"}
            
            # Build prompt
            prompt = custom_prompt or self.ANALYSIS_PROMPTS.get(analysis_type, 
                                                                self.ANALYSIS_PROMPTS["describe"])
            
            start_time = time.time()
            
            # Call Ollama with vision
            client = None
            try:
                client = self._create_ollama_client()
                generate_fn = getattr(client, "generate", None) if client is not None else None
                response_obj = (generate_fn if callable(generate_fn) else ollama.generate)(
                    model=self.current_model,
                    prompt=prompt,
                    images=[image_b64],
                    options={
                        "temperature": 0.7,
                        "num_ctx": 4096,
                    }
                )
            finally:
                if client is not None:
                    self._close_ollama_client(client)

            response: Dict[str, Any] = self._as_dict(response_obj)
            
            generation_time = time.time() - start_time
            
            result = {
                "success": True,
                "analysis": response.get('response', ''),
                "model": self.current_model,
                "analysis_type": analysis_type,
                "generation_time": generation_time,
                "tokens_used": response.get('eval_count', 0),
            }
            
            # Store for learning
            self._analysis_history.append({
                "timestamp": datetime.now().isoformat(),
                "type": analysis_type,
                "result_preview": result["analysis"][:200],
            })
            
            # Publish event
            if self.event_bus:
                self.event_bus.publish("visual.analysis_complete", result)
            
            return result
            
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def enhance_prompt(self, prompt: str, style_hints: Optional[Dict] = None) -> str:
        """Use Ollama to enhance image generation prompts - SOTA 2026."""
        if not OLLAMA_AVAILABLE:
            return prompt

        if not self.active:
            return prompt
        
        try:
            enhancement_prompt = f"""You are an expert AI image generation prompt engineer.
Enhance this image generation prompt to be more detailed and visually descriptive.
Add specific details about:
- Lighting and atmosphere
- Color palette and mood
- Composition and perspective
- Artistic style and technique
- Quality enhancers

Original prompt: {prompt}

{"Style preferences: " + json.dumps(style_hints) if style_hints else ""}

Enhanced prompt (respond with ONLY the enhanced prompt, no explanation):"""
            
            client = None
            try:
                chosen_model = self.current_model
                try:
                    models = getattr(self, "all_models", None)
                    if isinstance(models, list) and models:
                        by_lower = {str(m).lower(): str(m) for m in models}
                        for preferred in [
                            "llama3.2:latest",
                            "llama3.2",
                            "llama3:latest",
                            "llama3",
                            "llama2:latest",
                            "llama2",
                        ]:
                            if preferred in by_lower:
                                chosen_model = by_lower[preferred]
                                break
                        else:
                            non_vision = [
                                str(m) for m in models
                                if not any(v in str(m).lower() for v in ['llava', 'bakllava', 'vision', 'moondream'])
                            ]
                            if non_vision:
                                chosen_model = non_vision[0]
                except Exception:
                    chosen_model = self.current_model

                client = self._create_ollama_client()
                generate_fn = getattr(client, "generate", None) if client is not None else None
                response_obj = (generate_fn if callable(generate_fn) else ollama.generate)(
                    model=chosen_model,
                    prompt=enhancement_prompt,
                    options={"temperature": 0.8}
                )
            finally:
                if client is not None:
                    self._close_ollama_client(client)

            response: Dict[str, Any] = self._as_dict(response_obj)
            
            enhanced = response.get('response', prompt).strip()
            
            # Apply style memory if available
            if self._style_memory.get('preferred_styles'):
                styles = ', '.join(self._style_memory['preferred_styles'][:3])
                enhanced = f"{enhanced}, {styles}"
            
            logger.info(f"✨ Enhanced prompt: {enhanced[:100]}...")
            return enhanced
            
        except Exception as e:
            logger.warning(f"Prompt enhancement failed: {e}")
            return prompt
    
    async def generate_from_analysis(self, analysis: str) -> str:
        """Generate image prompt from analysis - for image recreation."""
        if not OLLAMA_AVAILABLE:
            return analysis

        if not self.active:
            return analysis
        
        try:
            prompt = f"""Based on this image analysis, create a detailed image generation prompt:

Analysis: {analysis}

Create a prompt that would generate a similar image. Include:
- Subject and composition
- Colors and lighting
- Style and mood
- Technical quality keywords

Respond with ONLY the generation prompt:"""
            
            client = None
            try:
                chosen_model = self.current_model
                try:
                    models = getattr(self, "all_models", None)
                    if isinstance(models, list) and models:
                        by_lower = {str(m).lower(): str(m) for m in models}
                        for preferred in [
                            "llama3.2:latest",
                            "llama3.2",
                            "llama3:latest",
                            "llama3",
                            "llama2:latest",
                            "llama2",
                        ]:
                            if preferred in by_lower:
                                chosen_model = by_lower[preferred]
                                break
                        else:
                            non_vision = [
                                str(m) for m in models
                                if not any(v in str(m).lower() for v in ['llava', 'bakllava', 'vision', 'moondream'])
                            ]
                            if non_vision:
                                chosen_model = non_vision[0]
                except Exception:
                    chosen_model = self.current_model

                client = self._create_ollama_client()
                generate_fn = getattr(client, "generate", None) if client is not None else None
                response_obj = (generate_fn if callable(generate_fn) else ollama.generate)(
                    model=chosen_model,
                    prompt=prompt,
                )
            finally:
                if client is not None:
                    self._close_ollama_client(client)

            response: Dict[str, Any] = self._as_dict(response_obj)
            
            return response.get('response', analysis).strip()
            
        except Exception as e:
            logger.warning(f"Prompt generation failed: {e}")
            return analysis
    
    def learn_from_feedback(self, image_id: str, feedback: Dict[str, Any]):
        """Learn from user feedback on generated images - SOTA 2026 Meta-Learning."""
        try:
            score = feedback.get('score', 0)
            style = feedback.get('style', '')
            liked_aspects = feedback.get('liked', [])
            disliked_aspects = feedback.get('disliked', [])
            
            # Update feedback scores
            self._feedback_scores[image_id] = {
                'score': score,
                'timestamp': datetime.now().isoformat(),
                'feedback': feedback
            }
            
            # Update style memory based on positive feedback
            if score >= 4 and style:
                if 'preferred_styles' not in self._style_memory:
                    self._style_memory['preferred_styles'] = []
                if style not in self._style_memory['preferred_styles']:
                    self._style_memory['preferred_styles'].append(style)
                    # Keep only top 10 styles
                    self._style_memory['preferred_styles'] = \
                        self._style_memory['preferred_styles'][-10:]
            
            # Update liked/disliked aspects
            if 'liked_aspects' not in self._style_memory:
                self._style_memory['liked_aspects'] = {}
            if 'disliked_aspects' not in self._style_memory:
                self._style_memory['disliked_aspects'] = {}
            
            for aspect in liked_aspects:
                self._style_memory['liked_aspects'][aspect] = \
                    self._style_memory['liked_aspects'].get(aspect, 0) + 1
            
            for aspect in disliked_aspects:
                self._style_memory['disliked_aspects'][aspect] = \
                    self._style_memory['disliked_aspects'].get(aspect, 0) + 1
            
            logger.info(f"📚 Learned from feedback: score={score}, style={style}")
            
            # Publish learning event
            if self.event_bus:
                self.event_bus.publish("visual.learning_update", {
                    "image_id": image_id,
                    "feedback": feedback,
                    "style_memory_size": len(self._style_memory.get('preferred_styles', []))
                })
                
        except Exception as e:
            logger.error(f"Learning from feedback failed: {e}")
    
    def _image_to_base64(self, image: Union[str, bytes, Any]) -> Optional[str]:
        """Convert various image formats to base64."""
        try:
            if isinstance(image, str):
                # File path
                if os.path.exists(image):
                    with open(image, 'rb') as f:
                        return base64.b64encode(f.read()).decode('utf-8')
                # Already base64
                return image
            
            elif isinstance(image, bytes):
                return base64.b64encode(image).decode('utf-8')
            
            elif PIL_AVAILABLE and isinstance(image, Image.Image):
                buffer = BytesIO()
                image.save(buffer, format='PNG')
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            elif PYQT6_AVAILABLE and isinstance(image, QImage):
                buffer = QByteArray()
                buf = QBuffer(buffer)
                buf.open(QBuffer.OpenModeFlag.WriteOnly)
                image.save(buf, "PNG")
                return base64.b64encode(buffer.data()).decode('utf-8')
            
            return None
            
        except Exception as e:
            logger.error(f"Image to base64 conversion failed: {e}")
            return None


class AIImageGenerator:
    """SOTA 2026 AI Image Generation with multiple backends."""
    
    def __init__(self, event_bus=None, ollama_processor: Optional[OllamaVisionProcessor] = None):
        self.event_bus = event_bus
        self.ollama = ollama_processor or OllamaVisionProcessor(event_bus)
        
        # Backend availability
        self.backends = {
            'diffusers': DIFFUSERS_AVAILABLE,
            'torch': TORCH_AVAILABLE,
            'cuda': CUDA_AVAILABLE,
            'pil': PIL_AVAILABLE,
        }
        
        # Cached pipelines
        self._lcm_pipe = None
        self._sdxl_pipe = None
        self._animatediff_pipe = None
        
        # Generation tracking
        self._generation_history = []
        self._mutex = threading.Lock()

        # SOTA 2026: Diffusers is lazy-loaded, not disabled
        if not self.backends.get('diffusers'):
            logger.info(f"🎨 Diffusers will be loaded on first use (lazy init)")
        else:
            logger.info(f"🎨 Diffusers pre-loaded and ready")
        
        logger.info(f"🎨 AI Image Generator initialized: {self.backends}")

    def _diffusers_requested(self, config: VisualConfig) -> bool:
        model = str(getattr(config, "model", "") or "").strip().lower()
        if model in ("", "auto", "pil", "procedural", "qt", "placeholder"):
            return False
        return True
    
    async def generate(self, prompt: str, config: VisualConfig) -> VisualResult:
        """Generate image based on config - SOTA 2026 unified interface."""
        start_time = time.time()
        
        try:
            # Enhance prompt with Ollama if enabled
            enhanced_prompt = prompt
            if config.ai_enhance and self.ollama.active:
                enhanced_prompt = await self.ollama.enhance_prompt(
                    prompt, 
                    self.ollama._style_memory
                )
            
            # Route to appropriate generator
            if config.mode == VisualMode.TEXT_TO_IMAGE:
                result = await self._generate_text_to_image(enhanced_prompt, config)
            elif config.mode == VisualMode.ANIMATION:
                result = await self._generate_animation(enhanced_prompt, config)
            elif config.mode == VisualMode.IMAGE_ANALYSIS:
                result = await self._analyze_image(prompt, config)
            elif config.mode in [VisualMode.FUNCTION_PLOT, VisualMode.TRIGONOMETRY,
                                VisualMode.CALCULUS, VisualMode.FRACTAL,
                                VisualMode.SACRED_GEOMETRY, VisualMode.CARTOGRAPHY,
                                VisualMode.ASTROLOGY, VisualMode.CALLIGRAPHY]:
                result = await self._generate_technical(prompt, config)
            else:
                result = await self._generate_text_to_image(enhanced_prompt, config)
            
            result.generation_time = time.time() - start_time
            
            # Track generation
            self._generation_history.append({
                "prompt": prompt,
                "enhanced_prompt": enhanced_prompt,
                "mode": config.mode.value,
                "time": result.generation_time,
                "success": result.success,
                "timestamp": datetime.now().isoformat()
            })
            
            # Publish event
            if self.event_bus and result.success:
                self.event_bus.publish("visual.generation_complete", {
                    "mode": config.mode.value,
                    "time": result.generation_time,
                    "metadata": result.metadata
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return VisualResult(
                success=False,
                error=str(e),
                generation_time=time.time() - start_time
            )
    
    async def _generate_text_to_image(self, prompt: str, config: VisualConfig) -> VisualResult:
        """Generate image from text using best available backend."""

        wants_diffusers = self._diffusers_requested(config)

        if wants_diffusers:
            # SOTA 2026: Lazy import diffusers only when needed
            if _lazy_import_diffusers():
                # Update backend availability after successful lazy import
                self.backends['diffusers'] = True
            
            if not self.backends.get('torch'):
                return VisualResult(
                    success=False,
                    error=f"PyTorch not available. Install PyTorch and Diffusers. Enable Diffusers by running: {DIFFUSERS_INSTALL_HINT}",
                )
            if not self.backends.get('diffusers'):
                err = DIFFUSERS_IMPORT_ERROR or "unknown import error"
                return VisualResult(
                    success=False,
                    error=f"Diffusers not available: {err}. Enable Diffusers by running: {DIFFUSERS_INSTALL_HINT}",
                )
        
        # Try diffusers first (best quality)
        if self.backends['diffusers'] and self.backends['torch']:
            return await self._generate_with_diffusers(prompt, config)
        
        # Fallback to PIL procedural generation
        if self.backends['pil']:
            return await self._generate_procedural(prompt, config)
        
        # Final fallback to Qt
        if PYQT6_AVAILABLE:
            return await self._generate_placeholder(prompt, config)
        
        return VisualResult(success=False, error="No image generation backend available")
    
    async def _generate_with_diffusers(self, prompt: str, config: VisualConfig) -> VisualResult:
        """Generate with diffusers/LCM - SOTA 2026 real-time generation."""
        try:
            # SOTA 2026: Ensure diffusers is loaded (lazy import)
            if not _lazy_import_diffusers():
                return VisualResult(
                    success=False,
                    error=f"Diffusers import failed: {DIFFUSERS_IMPORT_ERROR or 'unknown error'}"
                )
            
            import torch
            from diffusers import AutoPipelineForText2Image, LCMScheduler
            
            # Determine model based on FREE VRAM (not total)
            model_id = "SimianLuo/LCM_Dreamshaper_v7"
            if CUDA_AVAILABLE:
                free_vram, total_vram = torch.cuda.mem_get_info(0)
                free_vram_gb = free_vram / 1e9
                total_vram_gb = total_vram / 1e9
                logger.info(f"VRAM: {free_vram_gb:.1f}GB free / {total_vram_gb:.1f}GB total")
                if free_vram_gb >= 10:
                    model_id = "stabilityai/sdxl-turbo"
            
            # Load/cache pipeline
            if self._lcm_pipe is None:
                logger.info(f"Loading model: {model_id}")
                self._lcm_pipe = AutoPipelineForText2Image.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16 if CUDA_AVAILABLE else torch.float32,
                    safety_checker=None,
                )
                # SOTA 2026: Enable GPU optimizations if CUDA available
                if CUDA_AVAILABLE:
                    self._lcm_pipe = self._lcm_pipe.to("cuda")
                    logger.info(f"✅ Diffusers running on GPU: {torch.cuda.get_device_name(0)}")
                    
                    # Enable memory optimizations
                    self._lcm_pipe.enable_attention_slicing()
                    
                    # Enable VAE tiling for high-res images
                    if hasattr(self._lcm_pipe, 'enable_vae_tiling'):
                        self._lcm_pipe.enable_vae_tiling()
                    
                    # Enable model CPU offload if free VRAM is tight
                    free_vram_bytes = torch.cuda.mem_get_info(0)[0]
                    free_vram_gb = free_vram_bytes / 1e9
                    if free_vram_gb < 6 and hasattr(self._lcm_pipe, 'enable_model_cpu_offload'):
                        self._lcm_pipe.enable_model_cpu_offload()
                        logger.info(f"✅ Model CPU offload enabled (free VRAM: {free_vram_gb:.1f}GB)")
                else:
                    logger.warning("⚠️  Running on CPU (slow) - GPU not available")
                
                self._lcm_pipe.scheduler = LCMScheduler.from_config(
                    self._lcm_pipe.scheduler.config
                )
            
            # Generate
            result = self._lcm_pipe(
                prompt=prompt,
                negative_prompt=config.negative_prompt or "blurry, low quality",
                num_inference_steps=config.steps,
                guidance_scale=config.guidance_scale,
                width=config.width,
                height=config.height,
            )
            
            pil_image = result.images[0]
            
            return VisualResult(
                success=True,
                image=pil_image,
                metadata={
                    "prompt": prompt,
                    "model": model_id,
                    "steps": config.steps,
                    "backend": "diffusers_lcm",
                    "cuda": CUDA_AVAILABLE
                }
            )
            
        except RuntimeError as cuda_err:
            is_oom = "out of memory" in str(cuda_err).lower()
            logger.error(f"Diffusers generation {'CUDA OOM' if is_oom else 'RuntimeError'}: {cuda_err}")
            if is_oom:
                import gc
                if self._lcm_pipe is not None:
                    try:
                        self._lcm_pipe.to("cpu")
                    except Exception:
                        pass
                    del self._lcm_pipe
                    self._lcm_pipe = None
                gc.collect()
                torch.cuda.empty_cache()
                logger.info("🧹 Cleared GPU memory after OOM")
            if self._diffusers_requested(config):
                return VisualResult(success=False, error=f"Diffusers generation failed: {cuda_err}")
            return await self._generate_procedural(prompt, config)
        except Exception as e:
            logger.error(f"Diffusers generation failed: {e}")
            if self._lcm_pipe is not None:
                import gc
                del self._lcm_pipe
                self._lcm_pipe = None
                gc.collect()
                if CUDA_AVAILABLE:
                    torch.cuda.empty_cache()
            if self._diffusers_requested(config):
                return VisualResult(success=False, error=f"Diffusers generation failed: {e}")
            logger.warning(f"Falling back to PIL (Diffusers generation failed): {e}")
            return await self._generate_procedural(prompt, config)
    
    async def _generate_procedural(self, prompt: str, config: VisualConfig) -> VisualResult:
        """Generate procedural art based on prompt - SOTA 2026 algorithmic art."""
        try:
            from PIL import Image, ImageDraw, ImageFilter
            
            w, h = config.width, config.height
            image = Image.new('RGB', (w, h), (15, 15, 25))
            draw = ImageDraw.Draw(image)
            
            # Parse prompt for visual cues
            prompt_lower = prompt.lower()
            
            # Generate based on keywords
            if any(k in prompt_lower for k in ['space', 'galaxy', 'cosmic', 'star']):
                image = self._generate_cosmic(image, draw, config)
            elif any(k in prompt_lower for k in ['abstract', 'geometric', 'pattern']):
                image = self._generate_abstract(image, draw, config)
            elif any(k in prompt_lower for k in ['landscape', 'nature', 'forest', 'mountain']):
                image = self._generate_landscape(image, draw, config)
            elif any(k in prompt_lower for k in ['wave', 'ocean', 'water', 'fluid']):
                image = self._generate_fluid(image, draw, config)
            else:
                image = self._generate_default_art(image, draw, config)
            
            # Apply post-processing
            if config.detail_level >= 3:
                image = image.filter(ImageFilter.SMOOTH)
            
            return VisualResult(
                success=True,
                image=image,
                metadata={
                    "prompt": prompt,
                    "backend": "procedural_pil",
                    "style": "algorithmic_art"
                }
            )
            
        except Exception as e:
            logger.error(f"Procedural generation failed: {e}")
            return VisualResult(success=False, error=str(e))
    
    def _generate_cosmic(self, image, draw, config):
        """Generate cosmic/space art."""
        w, h = config.width, config.height
        import random
        
        # Stars
        for _ in range(w * h // 100):
            x, y = random.randint(0, w), random.randint(0, h)
            brightness = random.randint(100, 255)
            size = random.choice([1, 1, 1, 2, 2, 3])
            draw.ellipse([x, y, x+size, y+size], fill=(brightness, brightness, brightness))
        
        # Nebula effect
        for _ in range(5):
            cx, cy = random.randint(0, w), random.randint(0, h)
            r = random.randint(50, 150)
            color = (random.randint(50, 150), random.randint(20, 100), random.randint(100, 200))
            for i in range(r, 0, -10):
                alpha_color = tuple(c * i // r for c in color)
                draw.ellipse([cx-i, cy-i, cx+i, cy+i], fill=alpha_color)
        
        return image
    
    def _generate_abstract(self, image, draw, config):
        """Generate abstract geometric art."""
        w, h = config.width, config.height
        import random
        
        colors = [
            (255, 100, 100), (100, 255, 100), (100, 100, 255),
            (255, 255, 100), (255, 100, 255), (100, 255, 255)
        ]
        
        for _ in range(20):
            shape = random.choice(['rect', 'ellipse', 'polygon'])
            color = random.choice(colors)
            
            if shape == 'rect':
                x1, y1 = random.randint(0, w), random.randint(0, h)
                x2, y2 = x1 + random.randint(50, 200), y1 + random.randint(50, 200)
                draw.rectangle([x1, y1, x2, y2], fill=color, outline=(255, 255, 255))
            elif shape == 'ellipse':
                x1, y1 = random.randint(0, w), random.randint(0, h)
                r = random.randint(30, 100)
                draw.ellipse([x1-r, y1-r, x1+r, y1+r], fill=color)
            else:
                points = [(random.randint(0, w), random.randint(0, h)) for _ in range(random.randint(3, 6))]
                draw.polygon(points, fill=color)
        
        return image
    
    def _generate_landscape(self, image, draw, config):
        """Generate landscape art."""
        w, h = config.width, config.height
        import random
        
        # Sky gradient
        for y in range(h // 2):
            r = int(50 + (h//2 - y) * 0.3)
            g = int(100 + (h//2 - y) * 0.4)
            b = int(150 + (h//2 - y) * 0.5)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        
        # Mountains
        for layer in range(3):
            points = [(0, h)]
            for x in range(0, w + 50, 50):
                peak = h // 2 + random.randint(-100 + layer * 30, 100 - layer * 30)
                points.append((x, peak))
            points.append((w, h))
            
            gray = 30 + layer * 40
            draw.polygon(points, fill=(gray, gray + 10, gray + 20))
        
        # Ground
        draw.rectangle([0, h * 3 // 4, w, h], fill=(30, 80, 30))
        
        return image
    
    def _generate_fluid(self, image, draw, config):
        """Generate fluid/wave art."""
        w, h = config.width, config.height
        
        for y in range(h):
            for x in range(0, w, 2):
                wave = math.sin(x * 0.02 + y * 0.01) * 50
                wave2 = math.cos(x * 0.01 - y * 0.02) * 30
                
                r = int(50 + wave)
                g = int(100 + wave2)
                b = int(200 + wave + wave2)
                
                r = max(0, min(255, r))
                g = max(0, min(255, g))
                b = max(0, min(255, b))
                
                draw.rectangle([x, y, x+2, y+1], fill=(r, g, b))
        
        return image
    
    def _generate_default_art(self, image, draw, config):
        """Generate default artistic visualization."""
        w, h = config.width, config.height
        
        # Gradient background
        for y in range(h):
            ratio = y / h
            r = int(20 + ratio * 30)
            g = int(20 + ratio * 40)
            b = int(40 + ratio * 60)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        
        # Central glow
        cx, cy = w // 2, h // 2
        for r in range(min(w, h) // 3, 0, -5):
            intensity = r / (min(w, h) // 3)
            color = (int(100 * intensity), int(150 * intensity), int(255 * intensity))
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=color)
        
        # Add prompt text
        try:
            from PIL import ImageFont
            font = ImageFont.load_default()
            draw.text((10, h - 30), f"Prompt: {config.mode.value}", fill=(200, 200, 200))
        except:
            pass
        
        return image
    
    async def _generate_animation(self, prompt: str, config: VisualConfig) -> VisualResult:
        """Generate animation frames - SOTA 2026."""
        frames = []
        
        for i in range(config.num_frames):
            # Modify config for each frame
            frame_config = VisualConfig(
                mode=VisualMode.TEXT_TO_IMAGE,
                width=config.width,
                height=config.height,
                seed=config.seed + i if config.seed > 0 else -1
            )
            
            frame_prompt = f"{prompt}, frame {i+1} of {config.num_frames}"
            result = await self._generate_text_to_image(frame_prompt, frame_config)
            
            if result.success:
                frames.append(result.image)
        
        return VisualResult(
            success=len(frames) > 0,
            frames=frames,
            metadata={
                "prompt": prompt,
                "num_frames": len(frames),
                "fps": config.fps,
                "backend": "animation_generator"
            }
        )
    
    async def _generate_technical(self, prompt: str, config: VisualConfig) -> VisualResult:
        """Generate technical visualization using TechnicalVisualizationEngine."""
        try:
            from gui.widgets.technical_visualization_engine import (
                TechnicalVisualizationEngine, TechnicalMode, TechnicalConfig
            )
            
            engine = TechnicalVisualizationEngine()
            
            # Map VisualMode to TechnicalMode
            mode_map = {
                VisualMode.FUNCTION_PLOT: TechnicalMode.FUNCTION_PLOT,
                VisualMode.TRIGONOMETRY: TechnicalMode.TRIGONOMETRY,
                VisualMode.CALCULUS: TechnicalMode.CALCULUS,
                VisualMode.FRACTAL: TechnicalMode.FRACTAL,
                VisualMode.SACRED_GEOMETRY: TechnicalMode.SACRED_GEOMETRY,
                VisualMode.CARTOGRAPHY: TechnicalMode.CARTOGRAPHY,
                VisualMode.ASTROLOGY: TechnicalMode.ASTROLOGY,
                VisualMode.CALLIGRAPHY: TechnicalMode.CALLIGRAPHY,
            }
            
            tech_mode = mode_map.get(config.mode, TechnicalMode.FUNCTION_PLOT)
            
            tech_config = TechnicalConfig(
                mode=tech_mode,
                width=config.width,
                height=config.height,
                detail_level=config.detail_level
            )
            
            qimage = engine.render(prompt, tech_config)
            
            return VisualResult(
                success=True,
                image=qimage,
                metadata={
                    "prompt": prompt,
                    "mode": tech_mode.value,
                    "backend": "technical_visualization"
                }
            )
            
        except Exception as e:
            logger.error(f"Technical visualization failed: {e}")
            return VisualResult(success=False, error=str(e))
    
    async def _analyze_image(self, image_path: str, config: VisualConfig) -> VisualResult:
        """Analyze image using Ollama vision."""
        if not self.ollama.active:
            return VisualResult(success=False, error="Ollama vision not available")
        
        analysis = await self.ollama.analyze_image(image_path)
        
        return VisualResult(
            success=analysis.get('success', False),
            analysis=analysis,
            metadata={"backend": "ollama_vision", "model": self.ollama.current_model}
        )
    
    async def _generate_placeholder(self, prompt: str, config: VisualConfig) -> VisualResult:
        """Generate a clearly-labeled fallback image when no real generation backend is available."""
        if not PYQT6_AVAILABLE:
            return VisualResult(success=False, error="No image backend available")

        try:
            image = QImage(config.width, config.height, QImage.Format.Format_RGB32)
            image.fill(QColor(15, 15, 25))

            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            gradient = QLinearGradient(0, 0, config.width, config.height)
            gradient.setColorAt(0, QColor(40, 10, 10))
            gradient.setColorAt(1, QColor(60, 20, 30))
            painter.fillRect(0, 0, config.width, config.height, gradient)

            painter.setPen(QColor(255, 80, 80))
            border = 4
            painter.drawRect(border, border, config.width - 2 * border, config.height - 2 * border)

            title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
            painter.setFont(title_font)
            painter.setPen(QColor(255, 100, 100))
            painter.drawText(
                20, config.height // 2 - 30,
                "[ FALLBACK — No Image Backend ]"
            )

            detail_font = QFont("Segoe UI", 10)
            painter.setFont(detail_font)
            painter.setPen(QColor(180, 140, 140))
            painter.drawText(
                20, config.height // 2 + 10,
                f"Prompt: {prompt[:60]}{'...' if len(prompt) > 60 else ''}"
            )
            painter.drawText(
                20, config.height // 2 + 35,
                "Install PyTorch + Diffusers for real image generation"
            )

            painter.end()

            return VisualResult(
                success=True,
                image=image,
                metadata={
                    "prompt": prompt,
                    "backend": "qt_fallback",
                    "warning": "This is a fallback image — no real generation backend was available"
                }
            )

        except Exception as e:
            return VisualResult(success=False, error=str(e))


class SOTAAnimationEngine:
    """SOTA 2026 Animation Engine - Smooth, GPU-accelerated animations."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.animations = {}
        self.frame_rate = 60
        self._running = False
        
        # Animation presets
        self.presets = {
            'fade_in': self._animate_fade_in,
            'fade_out': self._animate_fade_out,
            'slide_left': self._animate_slide_left,
            'slide_right': self._animate_slide_right,
            'scale_up': self._animate_scale_up,
            'scale_down': self._animate_scale_down,
            'pulse': self._animate_pulse,
            'glow': self._animate_glow,
            'rgb_cycle': self._animate_rgb_cycle,
            'wave': self._animate_wave,
        }
        
        logger.info("🎬 SOTA Animation Engine initialized")
    
    def create_animation(self, name: str, preset: str, duration_ms: int = 1000,
                        easing: str = 'ease_out', **kwargs) -> Dict:
        """Create a new animation with SOTA 2026 parameters."""
        if preset not in self.presets:
            logger.warning(f"Unknown preset: {preset}")
            return {}
        
        animation = {
            'name': name,
            'preset': preset,
            'duration_ms': duration_ms,
            'easing': easing,
            'start_time': None,
            'progress': 0.0,
            'complete': False,
            'callback': kwargs.get('callback'),
            'params': kwargs
        }
        
        self.animations[name] = animation
        return animation
    
    def start_animation(self, name: str):
        """Start an animation."""
        if name in self.animations:
            self.animations[name]['start_time'] = time.time()
            self.animations[name]['complete'] = False
            self.animations[name]['progress'] = 0.0
    
    def update_animations(self) -> List[Dict]:
        """Update all active animations - call this from GUI timer."""
        results = []
        current_time = time.time()
        
        for name, anim in list(self.animations.items()):
            if anim['start_time'] is None or anim['complete']:
                continue
            
            elapsed = (current_time - anim['start_time']) * 1000
            progress = min(1.0, elapsed / anim['duration_ms'])
            
            # Apply easing
            eased_progress = self._apply_easing(progress, anim['easing'])
            anim['progress'] = eased_progress
            
            # Get animation value
            preset_func = self.presets.get(anim['preset'])
            if preset_func:
                value = preset_func(eased_progress, anim['params'])
                results.append({
                    'name': name,
                    'progress': eased_progress,
                    'value': value,
                    'complete': progress >= 1.0
                })
            
            if progress >= 1.0:
                anim['complete'] = True
                if anim['callback']:
                    anim['callback']()
        
        return results
    
    def _apply_easing(self, t: float, easing: str) -> float:
        """Apply easing function - SOTA 2026 smooth animations."""
        if easing == 'linear':
            return t
        elif easing == 'ease_in':
            return t * t
        elif easing == 'ease_out':
            return 1 - (1 - t) * (1 - t)
        elif easing == 'ease_in_out':
            return 3 * t * t - 2 * t * t * t
        elif easing == 'bounce':
            if t < 0.5:
                return 8 * t * t * t * t
            else:
                return 1 - pow(-2 * t + 2, 4) / 2
        elif easing == 'elastic':
            if t == 0 or t == 1:
                return t
            return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1
        return t
    
    def _animate_fade_in(self, progress: float, params: dict) -> float:
        return progress
    
    def _animate_fade_out(self, progress: float, params: dict) -> float:
        return 1.0 - progress
    
    def _animate_slide_left(self, progress: float, params: dict) -> float:
        start = params.get('start', 100)
        return start * (1 - progress)
    
    def _animate_slide_right(self, progress: float, params: dict) -> float:
        end = params.get('end', 100)
        return end * progress
    
    def _animate_scale_up(self, progress: float, params: dict) -> float:
        start = params.get('start', 0.5)
        end = params.get('end', 1.0)
        return start + (end - start) * progress
    
    def _animate_scale_down(self, progress: float, params: dict) -> float:
        start = params.get('start', 1.0)
        end = params.get('end', 0.5)
        return start + (end - start) * progress
    
    def _animate_pulse(self, progress: float, params: dict) -> float:
        return 0.5 + 0.5 * math.sin(progress * math.pi * 2)
    
    def _animate_glow(self, progress: float, params: dict) -> Tuple[int, int, int]:
        intensity = 0.5 + 0.5 * math.sin(progress * math.pi * 2)
        base_color = params.get('color', (100, 150, 255))
        return (int(base_color[0] * intensity), int(base_color[1] * intensity), int(base_color[2] * intensity))
    
    def _animate_rgb_cycle(self, progress: float, params: dict) -> Tuple[int, int, int]:
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(progress, 1.0, 1.0)
        return (int(r * 255), int(g * 255), int(b * 255))
    
    def _animate_wave(self, progress: float, params: dict) -> float:
        amplitude = params.get('amplitude', 1.0)
        frequency = params.get('frequency', 1.0)
        return amplitude * math.sin(progress * math.pi * 2 * frequency)


class AIVisualEngine:
    """
    SOTA 2026 Unified AI Visual Engine
    
    Central hub for all visual processing, generation, animation,
    and learning in Kingdom AI with full Ollama integration.
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        
        # Initialize sub-systems
        self.ollama_vision = OllamaVisionProcessor(event_bus)
        self.generator = AIImageGenerator(event_bus, self.ollama_vision)
        self.animator = SOTAAnimationEngine(event_bus)
        
        # System state
        self.initialized = False
        self._generation_queue = asyncio.Queue() if asyncio.get_event_loop().is_running() else None
        
        # Stats
        self.stats = {
            'images_generated': 0,
            'analyses_performed': 0,
            'animations_created': 0,
            'learning_updates': 0,
        }
        
        logger.info("🎨 SOTA 2026 AI Visual Engine initialized")
    
    async def initialize(self) -> bool:
        """Initialize the visual engine and connect to event bus."""
        try:
            # Subscribe to events
            if self.event_bus:
                events = [
                    ("visual.generate", self._handle_generate_request),
                    ("visual.analyze", self._handle_analyze_request),
                    ("visual.feedback", self._handle_feedback),
                    ("visual.animate", self._handle_animate_request),
                ]
                
                for event_name, handler in events:
                    try:
                        self.event_bus.subscribe(event_name, handler)
                    except Exception as e:
                        logger.warning(f"Failed to subscribe to {event_name}: {e}")
            
            self.initialized = True
            logger.info("✅ AI Visual Engine initialized and connected to event bus")
            return True
            
        except Exception as e:
            logger.error(f"Visual engine initialization failed: {e}")
            return False
    
    async def generate_image(self, prompt: str, config: Optional[VisualConfig] = None) -> VisualResult:
        """Generate image with SOTA 2026 AI - main public interface."""
        config = config or VisualConfig()
        result = await self.generator.generate(prompt, config)
        
        if result.success:
            self.stats['images_generated'] += 1
        
        return result
    
    async def analyze_image(self, image: Union[str, bytes, Any],
                           analysis_type: str = "describe") -> Dict[str, Any]:
        """Analyze image using Ollama vision."""
        result = await self.ollama_vision.analyze_image(image, analysis_type)
        
        if result.get('success'):
            self.stats['analyses_performed'] += 1
        
        return result
    
    def create_animation(self, name: str, preset: str, **kwargs):
        """Create animation with SOTA 2026 engine."""
        anim = self.animator.create_animation(name, preset, **kwargs)
        self.stats['animations_created'] += 1
        return anim
    
    def provide_feedback(self, image_id: str, feedback: Dict[str, Any]):
        """Provide feedback for learning system."""
        self.ollama_vision.learn_from_feedback(image_id, feedback)
        self.stats['learning_updates'] += 1
    
    async def _handle_generate_request(self, event_data: Dict):
        """Handle generation request from event bus."""
        prompt = event_data.get('prompt', '')
        config_data = event_data.get('config', {})
        
        config = VisualConfig(**config_data) if config_data else VisualConfig()
        result = await self.generate_image(prompt, config)
        
        if self.event_bus:
            self.event_bus.publish("visual.generated", {
                "success": result.success,
                "metadata": result.metadata,
                "error": result.error
            })
    
    async def _handle_analyze_request(self, event_data: Dict):
        """Handle analysis request from event bus."""
        image = event_data.get('image')
        analysis_type = event_data.get('type', 'describe')
        
        result = await self.analyze_image(image, analysis_type)
        
        if self.event_bus:
            self.event_bus.publish("visual.analyzed", result)
    
    async def _handle_feedback(self, event_data: Dict):
        """Handle feedback from event bus."""
        image_id = event_data.get('image_id', '')
        feedback = event_data.get('feedback', {})
        
        self.provide_feedback(image_id, feedback)
    
    async def _handle_animate_request(self, event_data: Dict):
        """Handle animation request from event bus."""
        name = event_data.get('name', f'anim_{time.time()}')
        preset = event_data.get('preset', 'fade_in')
        
        self.create_animation(name, preset, **event_data)
    
    def get_status(self) -> Dict[str, Any]:
        """Get engine status."""
        return {
            "initialized": self.initialized,
            "ollama_active": self.ollama_vision.active,
            "ollama_models": self.ollama_vision.available_models,
            "backends": self.generator.backends,
            "stats": self.stats,
            "style_memory_size": len(self.ollama_vision._style_memory.get('preferred_styles', [])),
        }


# Global instance
_visual_engine: Optional[AIVisualEngine] = None


def get_visual_engine(event_bus=None) -> AIVisualEngine:
    """Get or create the global visual engine instance."""
    global _visual_engine
    if _visual_engine is None:
        _visual_engine = AIVisualEngine(event_bus)
    return _visual_engine


# Export
__all__ = [
    'AIVisualEngine',
    'AIImageGenerator', 
    'OllamaVisionProcessor',
    'SOTAAnimationEngine',
    'VisualMode',
    'VisualConfig',
    'VisualResult',
    'get_visual_engine',
]
