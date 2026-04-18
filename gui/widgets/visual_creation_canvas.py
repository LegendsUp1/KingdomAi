"""
SOTA 2026 Visual Creation Canvas - UNIFIED MULTI-ENGINE ORCHESTRATION
======================================================================
Real-time AI creation widget that COMBINES ALL engines for complex creations.

UNIFIED ARCHITECTURE:
- Acts as orchestration HUB for all creation engines
- Intelligently routes requests to multiple engines
- Combines outputs into single cohesive result

SUPPORTED ENGINES:
- Visual Canvas: Image generation (FLUX.1, SD3.5, LCM)
- Cinema Engine: Video/movie generation
- Medical Reconstruction: CT/MRI → 3D models
- Animation Engine: Motion, physics, particles
- Unity Integration: 3D rendering, terrain, game assets
- Creative Engine: Maps, designs, schematics, blueprints

EXAMPLE WORKFLOWS:
1. "Create a holographic medical heart animation"
   → Medical Engine + Animation Engine + Cinema Engine
2. "Generate a fantasy world map with animated clouds"
   → Creative Engine + Animation Engine + Cinema Engine
3. "Create a cyberpunk city schematic with neon lights"
   → Creative Engine + Visual Canvas + Cinema Engine
"""

import logging
import subprocess
import time
import os
import asyncio
from pathlib import Path
from enum import Enum
from typing import Optional, Dict, Any, List

logger = logging.getLogger("KingdomAI.VisualCreationCanvas")


def _wsl_resolve_exe(name: str) -> str:
    """No-op on native Linux — returns name as-is."""
    return name


# PyQt6 imports
try:
    from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QStackedWidget, QFrame, QPushButton
    from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt, QTimer, QSize
    from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QFont
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False
    QWidget = object
    QObject = object
    QThread = object
    QLabel = object
    QImage = object
    QPixmap = object
    pyqtSignal = object
    Qt = object
    QTimer = object
    QSize = object
    QPainter = object
    QColor = object
    QFont = object
    QStackedWidget = object

# SOTA 2026: Import RealTimeVideoPlayer for continuous video playback
try:
    from gui.widgets.real_time_video_player import RealTimeVideoPlayer
    HAS_VIDEO_PLAYER = True
except ImportError:
    HAS_VIDEO_PLAYER = False
    RealTimeVideoPlayer = None

# SOTA 2026: Import AI Video Restorer for video restoration
try:
    from ai_video_restorer.pipeline import VideoRestorationPipeline
    from ai_video_restorer.config import PipelineConfig
    HAS_VIDEO_RESTORER = True
except ImportError:
    HAS_VIDEO_RESTORER = False
    VideoRestorationPipeline = None
    PipelineConfig = None

# Enums
class VisualMode(Enum):
    IMAGE = "image"
    ANIMATION = "animation"
    VIDEO = "video"
    VIDEO_RESTORATION = "video_restoration"  # SOTA 2026: AI Video Restorer

class VideoBackend(Enum):
    AUTO = "auto"
    ANIMATELCM = "animatelcm"
    MOCHI1 = "mochi1"
    SVD_XT = "svd_xt"
    HUNYUAN = "hunyuan"
    LTXVIDEO = "ltxvideo"

class QualityPreset(Enum):
    DRAFT = "draft"
    STANDARD = "standard"
    PRODUCTION = "production"
    CINEMATIC = "cinematic"

class GenerationConfig:
    """Generation configuration."""
    def __init__(self):
        self.steps = 25
        self.width = 512
        self.height = 512
        self.guidance_scale = 7.5
        self.num_frames = 16
        self.mode = 'image'  # 'image' or 'video'
        self.quality_preset = QualityPreset.PRODUCTION
        self.video_backend = VideoBackend.AUTO

class ImageGenerationWorker(QObject if HAS_PYQT6 else object):
    """Worker thread for image generation with all SOTA 2026 backends."""
    if HAS_PYQT6:
        generation_started = pyqtSignal(str)
        generation_progress = pyqtSignal(str, int, object)  # request_id, progress, preview_image (QImage)
        generation_complete = pyqtSignal(object, dict)  # image (QImage/PIL), metadata
        generation_error = pyqtSignal(str, str)  # request_id, error
        # Signal for thread-safe invocation from main thread
        _generate_signal = pyqtSignal(str, str, object)  # request_id, prompt, config
    
    def __init__(self, event_bus=None):
        if HAS_PYQT6:
            super().__init__()
            # Connect signal → slot so main thread can trigger generation on worker thread
            self._generate_signal.connect(self._on_generate_requested)
        self.event_bus = event_bus
        self._running = False
        self._backend_status = {}
        self._lcm_pipe = None
        self._pipe = None
        self._current_request = None
        self._creation_service_start_attempted = False
        self._check_backends()

    def _attempt_start_creation_service(self):
        """Attempt to auto-start creation_engine_service locally on native Linux."""
        try:
            import shutil
            python_bin = shutil.which('python3') or shutil.which('python')
            if not python_bin:
                logger.warning("⚠️ No Python interpreter found for creation service")
                return
            
            project_root = Path(__file__).resolve().parent.parent.parent
            service_script = project_root / "creation_engine_service.py"
            if not service_script.exists():
                logger.info("ℹ️ creation_engine_service.py not found, skipping auto-start")
                return
            
            subprocess.Popen(
                [python_bin, str(service_script)],
                stdout=open('/tmp/creation_engine_service.log', 'w'),
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=str(project_root),
                env={**os.environ, 'PYTHONPATH': f"{project_root}:{os.environ.get('PYTHONPATH', '')}"},
            )
            logger.info("🚀 Attempted auto-start of creation_engine_service locally")
        except Exception as e:
            logger.warning(f"⚠️ Could not auto-start creation service: {e}")

    def _dispatch_generate_to_worker(self, request_id: str, prompt: str):
        """Dispatch generation to worker thread once the thread is running."""
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker._generate_signal.emit(request_id, prompt, self._generation_config)
            logger.info(f"🎨 Generation dispatched to worker thread: {request_id} (mode={self._generation_config.mode})")
        else:
            logger.error("Worker thread failed to start")
    
    def _on_generate_requested(self, request_id: str, prompt: str, config):
        """Slot that runs on the worker thread when _generate_signal is emitted."""
        self.generate_image(request_id, prompt, config if config else None)
    
    def _get_exports_dir(self) -> Path:
        """Get a writable exports directory — ~/kingdom_ai_output/ on native Linux."""
        import tempfile
        primary_paths = [
            Path.home() / "kingdom_ai_output",
        ]
        for exports_dir in primary_paths:
            try:
                exports_dir.mkdir(parents=True, exist_ok=True)
                test_file = exports_dir / ".write_test"
                test_file.write_text("ok")
                test_file.unlink()
                return exports_dir
            except OSError:
                continue
        # Fallback to project exports dir
        try:
            _project_root = Path(__file__).resolve().parent.parent.parent
            exports_dir = _project_root / "exports" / "creations"
            exports_dir.mkdir(parents=True, exist_ok=True)
            return exports_dir
        except OSError as e:
            logger.warning(f"⚠️ Project exports dir not writable ({e}), using temp dir")
        # Last resort: temp directory
        fallback = Path(tempfile.gettempdir()) / "kingdom_ai_creations"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    
    def _check_backends(self):
        """Check all available backends - COMPLETE BACKEND CHECKING."""
        # SOTA 2026 FIX: Master guard - if ANY import triggers a cascade failure
        # (e.g. diffusers importing MT5Tokenizer from transformers), catch it
        # so the worker still initializes with partial backends.
        try:
            self._check_backends_inner()
        except Exception as e:
            logger.warning(f"⚠️ Backend check encountered error (non-fatal): {e}")
            # Ensure status dict exists even on total failure
            if not self._backend_status:
                self._backend_status = {}

    def _check_backends_inner(self):
        """Inner backend checking - separated for clean error handling."""
        # SOTA 2026 FIX: Neutralize spacy-transformers-compat shim modules.
        # When the full GUI stack loads (thoth_qt → spacy → spacy-transformers),
        # it patches transformers.tokenization_utils with a broken compat shim
        # that removes ExtensionsTrie, breaking ALL diffusers imports.
        # Fix: remove the compat shim so the real transformers module loads.
        import sys as _sys
        # Snapshot module dict to avoid "dictionary changed size during iteration"
        # while other imports happen concurrently during startup.
        _compat_keys = [
            k for k, mod in list(_sys.modules.items())
            if mod is not None and '<spacy-transformers-compat>' in repr(mod)
        ]
        for k in _compat_keys:
            logger.info(f"🔧 Removing spacy-transformers compat shim: {k}")
            del _sys.modules[k]
        
        # Check Redis Creation Engine Service (isolated environment) - PRIORITY #1
        # SOTA 2026 FIX: Verify the service is actually running, not just that Redis is reachable.
        # The service must set 'creation.service.status' = 'running' key when it starts.
        try:
            import redis
            redis_client = redis.Redis(host='localhost', port=6380, password='QuantumNexus2025', decode_responses=True, socket_timeout=2)
            redis_client.ping()
            # Check if the creation service process is actually running
            service_status = redis_client.get('creation.service.status')
            if service_status == 'running':
                self._backend_status['creation_service'] = True
                self._redis_client = redis_client
                logger.info("✅ Redis Creation Engine Service available (isolated environment - NO NUMPY CONFLICTS)")
            else:
                # Attempt a one-time service start when Redis is reachable but service is down.
                self._attempt_start_creation_service()
                try:
                    time.sleep(1.0)
                    service_status = redis_client.get('creation.service.status')
                except Exception:
                    pass
                if service_status == 'running':
                    self._backend_status['creation_service'] = True
                    self._redis_client = redis_client
                    logger.info("✅ Redis Creation Engine Service auto-started and ready")
                    return
                self._backend_status['creation_service'] = False
                self._redis_client = None
                logger.info(f"ℹ️ Redis reachable but creation service not running (status={service_status}). Will use local backends.")
        except Exception as e:
            self._backend_status['creation_service'] = False
            self._redis_client = None
            logger.warning(f"⚠️ Redis Creation Engine Service not available: {e}")
        
        # Check Redis Video Generation Service (kingdom-video environment) - SOTA 2026
        # SOTA 2026 FIX: Same verification — service must set 'video.service.status' key.
        try:
            import redis
            video_redis = redis.Redis(host='localhost', port=6380, password='QuantumNexus2025', decode_responses=True, socket_timeout=2)
            video_redis.ping()
            video_status = video_redis.get('video.service.status')
            if video_status == 'running':
                self._backend_status['video_service'] = True
                self._video_redis_client = video_redis
                logger.info("✅ Redis Video Generation Service available (kingdom-video environment)")
            else:
                self._backend_status['video_service'] = False
                self._video_redis_client = None
                logger.info(f"ℹ️ Redis reachable but video service not running (status={video_status}). Will use local backends.")
        except Exception as e:
            self._backend_status['video_service'] = False
            self._video_redis_client = None
            logger.warning(f"⚠️ Redis Video Generation Service not available: {e}")
        
        # Disable cuDNN to prevent crashes
        try:
            import torch
            torch.backends.cudnn.enabled = False
            torch.backends.cudnn.benchmark = False
            logger.info("? cuDNN disabled in PyTorch backend to prevent crashes")
        except:
            pass
        
        # Check CUDA
        try:
            import torch
            self._backend_status['cuda'] = torch.cuda.is_available()
            if self._backend_status['cuda']:
                self._backend_status['gpu_name'] = torch.cuda.get_device_name(0)
                logger.info(f"? CUDA available: {self._backend_status['gpu_name']}")
            else:
                logger.info("?? CUDA not available")
        except:
            self._backend_status['cuda'] = False
        
        # Check Diffusers availability
        # SOTA 2026 FIX: Use find_spec() to check if packages are INSTALLED
        # without triggering any imports that hit spacy-transformers-compat.
        # Actual imports happen at generation time with compat neutralization.
        import importlib.util
        diffusers_spec = importlib.util.find_spec('diffusers')
        torch_spec = importlib.util.find_spec('torch')
        if diffusers_spec and torch_spec:
            self._backend_status['diffusers'] = True
            logger.info(f"✅ Diffusers + PyTorch packages found (installed)")
        else:
            self._backend_status['diffusers'] = False
            missing = []
            if not diffusers_spec: missing.append('diffusers')
            if not torch_spec: missing.append('torch')
            logger.warning(f"⚠️ Missing packages: {', '.join(missing)}")
        
        # =================================================================
        # SOTA 2026 IMAGE GENERATION BACKENDS
        # =================================================================
        
        # Check FLUX.1
        try:
            from diffusers import FluxPipeline
            self._backend_status['flux1'] = True
            logger.info("✅ FLUX.1 backend available (12B params, best quality)")
        except Exception:
            self._backend_status['flux1'] = False
            logger.info("ℹ️ FLUX.1 not available")
        
        # Check SD3.5
        try:
            from diffusers import StableDiffusion3Pipeline
            self._backend_status['sd35'] = True
            logger.info("✅ SD3.5 backend available (8B params, fine-tunable)")
        except Exception:
            self._backend_status['sd35'] = False
            logger.info("ℹ️ SD3.5 not available")
        
        # Check SDXL Turbo (use DiffusionPipeline, not AutoPipelineForText2Image)
        self._backend_status['sdxl_turbo'] = self._backend_status.get('diffusers', False)
        
        # =================================================================
        # SOTA 2026 VIDEO GENERATION BACKENDS
        # =================================================================
        
        # Check AnimateDiff/AnimateLCM
        try:
            from diffusers import AnimateDiffPipeline, MotionAdapter
            self._backend_status['animatelcm'] = True
            logger.info("✅ AnimateLCM backend available (fast 4-step animation)")
        except Exception:
            self._backend_status['animatelcm'] = False
            logger.info("ℹ️ AnimateLCM not available")
        
        # Check Mochi 1
        try:
            from diffusers import MochiPipeline
            self._backend_status['mochi1'] = True
            logger.info("✅ Mochi 1 backend available (10B params, production quality)")
        except Exception:
            self._backend_status['mochi1'] = False
            logger.info("ℹ️ Mochi 1 not available")
        
        # Check CogVideoX
        try:
            from diffusers import CogVideoXPipeline
            self._backend_status['cogvideox'] = True
            logger.info("✅ CogVideoX backend available (5B params, 3D attention)")
        except Exception:
            self._backend_status['cogvideox'] = False
            logger.info("ℹ️ CogVideoX not available")
        
        # Check LTXVideo
        try:
            from diffusers import LTXPipeline
            self._backend_status['ltxvideo'] = True
            logger.info("✅ LTXVideo backend available (real-time generation)")
        except Exception:
            self._backend_status['ltxvideo'] = False
            logger.info("ℹ️ LTXVideo not available")
        
        # Check SVD-XT
        try:
            from diffusers import StableVideoDiffusionPipeline
            self._backend_status['svd_xt'] = True
            logger.info("✅ SVD-XT backend available (image-to-video)")
        except Exception:
            self._backend_status['svd_xt'] = False
            logger.info("ℹ️ SVD-XT not available")
        
        # Check HunyuanVideo (requires separate installation)
        try:
            from diffusers import HunyuanVideoPipeline
            self._backend_status['hunyuan'] = True
            logger.info("✅ HunyuanVideo backend available (13B params, cinematic)")
        except Exception:
            self._backend_status['hunyuan'] = False
            logger.info("ℹ️ HunyuanVideo not available")
        
        # Check ComfyUI API
        try:
            import requests
            self._backend_status['comfyui'] = True
            logger.info("? ComfyUI API backend available (client)")
        except:
            self._backend_status['comfyui'] = False
        
        # Check Ollama
        try:
            import ollama
            self._backend_status['ollama'] = True
            logger.info("? Ollama client available (server check skipped)")
        except:
            self._backend_status['ollama'] = False
        
        # Emit backend status summary - SOTA 2026
        diffusers_ok = self._backend_status.get('diffusers', False)
        cuda_ok = self._backend_status.get('cuda', False)
        ollama_ok = self._backend_status.get('ollama', False)
        
        # Count available image backends
        image_backends = ['flux1', 'sd35', 'sdxl_turbo', 'diffusers']
        image_count = sum(1 for b in image_backends if self._backend_status.get(b, False))
        
        # Count available video backends
        video_backends = ['mochi1', 'cogvideox', 'ltxvideo', 'animatelcm', 'svd_xt', 'hunyuan']
        video_count = sum(1 for b in video_backends if self._backend_status.get(b, False))
        
        logger.info(f"📊 SOTA 2026 Backend Summary:")
        logger.info(f"   Image backends: {image_count} available (FLUX.1, SD3.5, SDXL Turbo, LCM)")
        logger.info(f"   Video backends: {video_count} available (Mochi, CogVideoX, LTX, AnimateLCM, SVD-XT)")
        logger.info(f"   CUDA: {'✅' if cuda_ok else '❌'}, Ollama: {'✅' if ollama_ok else '❌'}")
    
    def generate_image(self, request_id: str, prompt: str, config: Optional[GenerationConfig] = None):
        """Generate image or video using best available backend."""
        if not HAS_PYQT6:
            return
        
        self._running = True
        self._current_request = request_id
        
        if self.generation_started:
            self.generation_started.emit(request_id)
        
        # Check if video mode requested
        mode = getattr(config, 'mode', 'image') if config else 'image'
        
        try:
            # VIDEO MODE: Route to AnimateLCM pipeline
            if mode == 'video' and self._backend_status.get('diffusers', False):
                logger.info(f"🎬 Video mode — routing to AnimateLCM")
                self._generate_video_with_diffusers(request_id, prompt, config)
                return
            
            # IMAGE MODE: Priority routing
            # PRIORITY #1: Try Redis Creation Engine Service (isolated environment)
            if self._backend_status.get('creation_service', False) and self._redis_client:
                logger.info(f"🎨 Using Redis Creation Engine Service (isolated environment)")
                self._generate_with_redis_service(request_id, prompt, config)
            # FALLBACK #2: Try local Diffusers/LCM 
            elif self._backend_status.get('diffusers', False):
                logger.info(f"🎨 Using local Diffusers (may have NumPy conflicts)")
                self._generate_with_diffusers(request_id, prompt, config)
            # FALLBACK #3: Ollama
            elif self._backend_status.get('ollama', False):
                self._generate_with_ollama(request_id, prompt, config)
            # FALLBACK #4: Placeholder
            else:
                logger.warning("⚠️ No AI backends available - generating placeholder")
                self._generate_placeholder(request_id, prompt, config)
                
        except Exception as e:
            logger.error(f"Generation error: {e}", exc_info=True)
            if self.generation_error:
                self.generation_error.emit(request_id, str(e))
            if self.event_bus:
                self.event_bus.publish("visual.generation.error", {
                    "request_id": request_id,
                    "error": str(e)
                })
        finally:
            self._running = False
            self._current_request = None
    
    def _generate_with_diffusers(self, request_id: str, prompt: str, config: Optional[GenerationConfig] = None):
        """Generate using Diffusers backend — full quality DreamShaper 8 pipeline.
        
        SOTA 2026: Official HuggingFace recipe for Lykon/dreamshaper-8:
        - DEISMultistepScheduler (high-quality multi-step scheduler)
        - 25 inference steps (official recommendation)
        - fp16 precision (~3.5GB VRAM, fits RTX 4060 8GB)
        - guidance_scale 7.5 (SD1.5 default, good prompt adherence)
        - 512x512 native resolution
        """
        logger.info(f"🎨 VisualCreationCanvas worker: _generate_with_diffusers START")
        
        # SOTA 2026 FIX: Neutralize spacy-transformers-compat shim before sub-imports.
        import sys as _sys
        _compat_keys = [k for k in list(_sys.modules.keys())
                        if _sys.modules.get(k) is not None
                        and '<spacy-transformers-compat>' in repr(_sys.modules[k])]
        for k in _compat_keys:
            logger.info(f"🔧 Removing spacy-transformers compat shim: {k}")
            del _sys.modules[k]
        
        try:
            from diffusers import DiffusionPipeline, DEISMultistepScheduler
        except Exception as e:
            logger.error(f"❌ Diffusers sub-import failed even after compat fix: {e}")
            logger.info("Falling back to placeholder")
            return self._generate_placeholder(request_id, prompt, config)
        
        import torch
        from PIL import Image
        import numpy as np
        
        # Load or reuse pipeline
        if self._lcm_pipe is None:
            # Official HuggingFace recipe: Lykon/dreamshaper-8 + DEISMultistepScheduler
            # ~3.5GB VRAM in fp16 — fits well within RTX 4060 8GB budget
            logger.info("🎨 Loading DreamShaper 8 (full quality, ~3.5GB VRAM fp16)")
            model_id = "Lykon/dreamshaper-8"
            
            dtype = torch.float16 if self._backend_status.get('cuda') else torch.float32
            
            self._lcm_pipe = DiffusionPipeline.from_pretrained(
                model_id,
                torch_dtype=dtype,
                safety_checker=None,
                variant="fp16" if self._backend_status.get('cuda') else None
            )
            
            # SOTA 2026: DEISMultistepScheduler — official recommended scheduler
            self._lcm_pipe.scheduler = DEISMultistepScheduler.from_config(
                self._lcm_pipe.scheduler.config
            )
            
            # SOTA 2026 VRAM FIX: Use CPU offload instead of .to(cuda)
        
        # Use the initialized image pipeline consistently in callbacks and generation.
        pipe = self._lcm_pipe
        if pipe is None:
            raise RuntimeError("Image generation pipeline failed to initialize")

        # Clear VRAM before generation to prevent OOM
        if self._backend_status.get('cuda'):
            torch.cuda.empty_cache()
        
        # Official parameters: 25 steps, guidance 7.5, 512x512 native
        steps = config.steps if config else 25
        width = config.width if config else 512
        height = config.height if config else 512
        guidance_scale = config.guidance_scale if config else 7.5
        
        logger.info(f"?? Diffusers inference starting: steps={steps}, size={width}x{height}, cuda={self._backend_status.get('cuda')}")
        
        # Setup exports directory — with fallback to temp dir for WinError 1920
        exports_dir = self._get_exports_dir()
        
        # Progress callback for preview generation
        def progress_callback(step, timestep, latents):
            try:
                progress = int(10 + ((step + 1) / steps) * 80)  # 10-90%
                
                # Generate preview from latents every few steps
                if step % max(1, steps // 10) == 0 and latents is not None:
                    preview_image = self._latents_to_preview(latents, pipe)
                    if preview_image:
                        # Save preview
                        preview_path = exports_dir / f"preview_{request_id}_{step}.png"
                        preview_image.save(str(preview_path))
                        
                        # Emit progress with preview path
                        if self.event_bus:
                            self.event_bus.publish("visual.generation.progress", {
                                "request_id": request_id,
                                "progress": progress,
                                "preview_path": str(preview_path)
                            })
                        
                        # Emit QImage preview via signal
                        if HAS_PYQT6 and self.generation_progress:
                            qimage = self._pil_to_qimage(preview_image)
                            if qimage:
                                self.generation_progress.emit(request_id, progress, qimage)
                else:
                    # Emit progress without preview
                    if self.event_bus:
                        self.event_bus.publish("visual.generation.progress", {
                            "request_id": request_id,
                            "progress": progress
                        })
            except Exception as e:
                logger.debug(f"Progress callback error: {e}")
        
        # Generate image with timeout protection
        try:
            import threading
            
            generation_done = threading.Event()
            generation_result = [None]
            generation_error_holder = [None]
            
            def _run_pipe():
                try:
                    generation_result[0] = pipe(
                        prompt=prompt,
                        negative_prompt="blurry, low quality, distorted",
                        num_inference_steps=steps,
                        guidance_scale=guidance_scale,
                        width=width,
                        height=height,
                        callback=progress_callback,
                        callback_steps=1,
                    )
                except RuntimeError as cuda_err:
                    if "out of memory" in str(cuda_err).lower():
                        logger.error(f"CUDA OOM during diffusers generation: {cuda_err}")
                        import torch, gc
                        if self._lcm_pipe is not None:
                            try:
                                self._lcm_pipe.to("cpu")
                            except Exception:
                                pass
                            del self._lcm_pipe
                            self._lcm_pipe = None
                        gc.collect()
                        torch.cuda.empty_cache()
                    generation_error_holder[0] = cuda_err
                except Exception as ex:
                    generation_error_holder[0] = ex
                finally:
                    generation_done.set()
            
            gen_thread = threading.Thread(target=_run_pipe, daemon=True, name="DiffusersGen")
            gen_thread.start()
            
            # Heartbeat: publish progress while waiting so UI never looks frozen
            heartbeat_pct = 92
            while not generation_done.wait(timeout=5.0):
                if self.event_bus:
                    self.event_bus.publish("visual.generation.progress", {
                        "request_id": request_id,
                        "progress": min(heartbeat_pct, 99),
                        "step": "Generating..."
                    })
                    heartbeat_pct = min(heartbeat_pct + 1, 99)
            
            if generation_error_holder[0] is not None:
                raise generation_error_holder[0]
            
            result = generation_result[0]
            if result is None or not hasattr(result, 'images'):
                raise RuntimeError("Generation produced no output")
                
        except Exception as e:
            logger.error(f"Diffusers generation error: {e}")
            if self.generation_error:
                self.generation_error.emit(request_id, str(e))
            if self.event_bus:
                self.event_bus.publish("visual.generation.error", {
                    "request_id": request_id,
                    "error": str(e)
                })
                self.event_bus.publish("visual.generation.progress", {
                    "request_id": request_id,
                    "progress": 0,
                    "step": f"Failed: {str(e)[:60]}"
                })
            return
        
        image = result.images[0]
        
        # Save final image
        timestamp = int(time.time() * 1000)
        image_path = exports_dir / f"kingdom_ai_visual_{timestamp}_gen_{timestamp % 10000}.png"
        image.save(str(image_path))
        
        logger.info(f"? VisualCreationCanvas worker: Diffusers/DreamShaper-8 SUCCESS")
        logger.info(f"?? Real AI image saved: {image_path}")
        
        # Convert PIL to QImage
        qimage = self._pil_to_qimage(image)
        
        # Emit completion
        metadata = {
            "backend": "diffusers/dreamshaper-8",
            "image_path": str(image_path),
            "width": width,
            "height": height,
            "steps": steps,
            "prompt": prompt,
            "request_id": request_id
        }
        
        if self.generation_complete and qimage:
            self.generation_complete.emit(qimage, metadata)
        
        # Publish to EventBus
        if self.event_bus:
            self.event_bus.publish("visual.generated", {
                "image_path": str(image_path),
                "request_id": request_id,
                "prompt": prompt,
                "backend": "diffusers/dreamshaper-8",
                "width": width,
                "height": height,
                "steps": steps
            })
            
            # Final progress update
            self.event_bus.publish("visual.generation.progress", {
                "request_id": request_id,
                "progress": 100,
                "preview_path": str(image_path)
            })
    
    def _generate_video_with_diffusers(self, request_id: str, prompt: str, config: Optional[GenerationConfig] = None):
        """Generate video using AnimateLCM — 16 frames, 6 steps, fits 8GB VRAM.
        
        SOTA 2026: Official HuggingFace AnimateLCM recipe:
        - MotionAdapter: wangfuyun/AnimateLCM
        - Base model: Lykon/dreamshaper-8 (SD1.5 fine-tune)
        - LCM LoRA for fast inference (6 steps)
        - 16 frames at 512x512
        - CPU offload + VAE slicing for 8GB VRAM
        """
        logger.info(f"🎬 VisualCreationCanvas worker: _generate_video_with_diffusers START")
        
        # Neutralize spacy-transformers-compat shim
        import sys as _sys
        _compat_keys = [k for k in list(_sys.modules.keys())
                        if _sys.modules.get(k) is not None
                        and '<spacy-transformers-compat>' in repr(_sys.modules[k])]
        for k in _compat_keys:
            del _sys.modules[k]
        
        p_early = (prompt or "").lower()
        engineering_tokens = ("exploded", "exploded view", "disassembled", "assembly", "parts",
                              "schematic", "blueprint", "technical", "cad", "3d model",
                              "design", "construct", "build", "engineering")
        mech_tokens = ("car", "supercar", "engine", "mechanical", "machine", "turbine", "drone", "robot",
                       "plane", "airplane", "jet", "helicopter", "rocket", "ship", "boat", "submarine",
                       "motorcycle", "bike", "truck", "vehicle",
                       "shoe", "boot", "sneaker", "helmet", "armor", "backpack", "glove",
                       "sword", "gun", "rifle", "pistol", "blade", "shield", "axe",
                       "phone", "laptop", "tablet", "camera", "computer", "keyboard",
                       "chair", "table", "desk", "shelf", "cabinet", "sofa", "bed",
                       "house", "building", "tower", "castle", "bridge",
                       "tree", "flower", "plant", "mushroom",
                       "cat", "dog", "horse", "bird", "dragon", "dinosaur", "fish",
                       "gear", "piston", "turbine", "pump", "generator",
                       "mech", "android", "cyborg")
        is_engineering_exploded = any(t in p_early for t in engineering_tokens) and any(t in p_early for t in mech_tokens)

        # Engineering path should not block on heavy diffusion model boot.
        if is_engineering_exploded:
            try:
                from PIL import Image

                num_frames = 48
                if any(k in p_early for k in ("frame by frame", "every frame", "slow build", "step by step")):
                    num_frames = 72
                if any(k in p_early for k in ("high quality", "ultra", "cinematic", "detailed")):
                    num_frames = max(num_frames, 84)
                width = 640 if any(k in p_early for k in ("high quality", "ultra", "cinematic", "detailed")) else 540
                height = 640 if width >= 600 else 540
                fps_target = 7 if "slow" in p_early else 9

                if self.event_bus:
                    self.event_bus.publish("visual.generation.started", {
                        "request_id": request_id,
                        "message": f"Engineering build/exploded sequence: {prompt[:60]}..."
                    })
                    self.event_bus.publish("visual.generation.progress", {
                        "request_id": request_id,
                        "progress": 15
                    })

                frames = self._generate_engineering_exploded_with_libraries(
                    request_id=request_id,
                    prompt=prompt,
                    total_frames=num_frames,
                    width=width,
                    height=height,
                )
                if not frames:
                    logger.warning("Engineering CAD renderer returned no frames; falling back to standard video path")
                else:
                    exports_dir = self._get_exports_dir()
                    timestamp = int(time.time() * 1000)
                    first = frames[0]
                    video_path, gif_fallback = self._encode_video_from_frames(
                        frames=frames,
                        exports_dir=exports_dir,
                        stem=f"kingdom_ai_video_{timestamp}",
                        fps=fps_target,
                    )
                    logger.info(f"🎬 Video saved: {video_path} ({len(frames)} frames @ {fps_target} fps)")
                    qimage = self._pil_to_qimage(first)
                    metadata = {
                        "backend": "cadquery+trimesh_engineering",
                        "image_path": str(video_path),
                        "video_path": str(video_path),
                        "preview_gif_path": str(gif_fallback) if gif_fallback else "",
                        "width": width,
                        "height": height,
                        "num_frames": len(frames),
                        "fps": fps_target,
                        "prompt": prompt,
                        "request_id": request_id,
                        "type": "video",
                    }
                    if self.generation_complete and qimage:
                        self.generation_complete.emit(qimage, metadata)
                    if self.event_bus:
                        self.event_bus.publish("visual.generated", {
                            "image_path": str(video_path),
                            "video_path": str(video_path),
                            "preview_gif_path": str(gif_fallback) if gif_fallback else "",
                            "request_id": request_id,
                            "prompt": prompt,
                            "backend": "cadquery+trimesh_engineering",
                            "type": "video",
                            "num_frames": len(frames),
                            "width": width,
                            "height": height,
                            "fps": fps_target,
                        })
                        self.event_bus.publish("visual.generation.progress", {
                            "request_id": request_id,
                            "progress": 100,
                            "preview_path": str(video_path),
                        })
                    return
            except Exception as e:
                logger.error(f"Engineering direct video path failed: {e}", exc_info=True)
                # fall through to standard pipeline

        try:
            from diffusers import AnimateDiffPipeline, LCMScheduler, MotionAdapter
        except Exception as e:
            logger.error(f"❌ AnimateDiff import failed: {e}")
            logger.info("Falling back to image generation")
            return self._generate_with_diffusers(request_id, prompt, config)
        
        import torch
        import gc
        
        # FREE ALL GPU memory before video pipeline
        if self._lcm_pipe is not None:
            logger.info("🔄 Unloading image pipeline to free VRAM for video...")
            try:
                self._lcm_pipe.to("cpu")
            except Exception:
                pass
            del self._lcm_pipe
            self._lcm_pipe = None
        if self._pipe is not None:
            try:
                self._pipe.to("cpu")
            except Exception:
                pass
            del self._pipe
            self._pipe = None
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        # Explicitly reset the video GPU (GPU 1) to avoid fragmentation from canvas init
        video_gpu = 1 if torch.cuda.device_count() > 1 else 0
        with torch.cuda.device(video_gpu):
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
        logger.info(f"🧹 VRAM after cleanup: GPU0={torch.cuda.memory_allocated(0)/1e6:.0f}MB GPU{video_gpu}={torch.cuda.memory_allocated(video_gpu)/1e6:.0f}MB")
        
        # Load or reuse video pipeline
        if not hasattr(self, '_video_pipe') or self._video_pipe is None:
            logger.info("🎬 Loading AnimateLCM to CPU first (zero GPU during load)")
            
            # Load motion adapter to CPU
            adapter = MotionAdapter.from_pretrained(
                "wangfuyun/AnimateLCM",
                torch_dtype=torch.float16
            )
            
            # SOTA: epiCRealism — official AnimateLCM recommended base (photorealistic)
            self._video_pipe = AnimateDiffPipeline.from_pretrained(
                "emilianJR/epiCRealism",
                motion_adapter=adapter,
                torch_dtype=torch.float16,
                low_cpu_mem_usage=True,
            )
            
            # LCM scheduler for fast inference
            self._video_pipe.scheduler = LCMScheduler.from_config(
                self._video_pipe.scheduler.config,
                beta_schedule="linear"
            )
            
            # Load LCM LoRA weights
            self._video_pipe.load_lora_weights(
                "wangfuyun/AnimateLCM",
                weight_name="AnimateLCM_sd15_t2v_lora.safetensors",
                adapter_name="lcm-lora"
            )
            
            # VRAM: sequential offload + VAE tiling for 512x512 on 6GB
            video_gpu = 1 if torch.cuda.device_count() > 1 else 0
            self._video_pipe.enable_vae_slicing()
            self._video_pipe.enable_vae_tiling()
            self._video_pipe.enable_sequential_cpu_offload(gpu_id=video_gpu)
            
            # FreeInit — iterative latent refinement for quality
            self._video_pipe.enable_free_init(method="butterworth", use_fast_sampling=True)
            
            logger.info(f"✅ SOTA AnimateLCM + epiCRealism + FreeInit on GPU {video_gpu}")
        
        pipe = self._video_pipe
        
        # Final VRAM cleanup
        gc.collect()
        torch.cuda.empty_cache()
        
        # SOTA HQ: 512x512 native SD1.5 res, 16 frames, 8 steps, FreeInit
        num_frames = 16
        steps = 8  # More steps = cleaner output
        guidance_scale = 2.0  # Slightly higher for better prompt adherence (color accuracy)
        width = 512  # Native SD1.5 resolution
        height = 512  # No more pixelation
        
        logger.info(f"� SOTA Video: {num_frames} frames, {steps} steps, {width}x{height}, FreeInit ON")
        
        try:
            # Emit start
            if self.event_bus:
                self.event_bus.publish("visual.generation.started", {
                    "request_id": request_id,
                    "message": f"Video: {prompt[:60]}..."
                })
            
            # Prompt understanding profiles for better semantic control.
            import re
            p = prompt.lower()
            exploded_tokens = [
                "exploded", "exploded view", "blown apart diagram", "assembly diagram",
                "disassembled", "parts separated", "component breakdown", "cutaway"
            ]
            motion_tokens = [
                "moving", "motion", "animate", "animation", "rotating", "turntable", "kinematic"
            ]
            liquid_tokens = ["water", "liquid", "drink", "beverage", "splash", "droplets"]
            mechanical_tokens = [
                "engine", "gear", "gearbox", "car", "supercar", "machine", "turbine",
                "piston", "mechanical", "industrial", "assembly",
                "plane", "airplane", "jet", "helicopter", "rocket", "ship", "boat",
                "motorcycle", "drone", "robot", "mech",
                "shoe", "helmet", "sword", "gun", "phone", "laptop", "camera",
                "chair", "table", "house", "building", "tower",
                "cat", "dog", "horse", "bird", "dragon", "tree", "flower",
            ]
            has_exploded = any(t in p for t in exploded_tokens)
            has_motion = any(t in p for t in motion_tokens)
            has_mechanical = any(t in p for t in mechanical_tokens)
            has_liquid = any(t in p for t in liquid_tokens)
            color_match = re.search(r'(?:color(?:\s+is)?\s+|colou?red?\s+)(\w+)', prompt, re.IGNORECASE)
            color_word = color_match.group(1) if color_match else None

            profile = "default"
            if has_exploded and has_mechanical:
                # Engineering-specific profile for exploded moving parts.
                profile = "engineering_exploded"
                steps = max(steps, 10)
                guidance_scale = 3.0
                enhanced_prompt = (
                    f"engineering exploded view animation, disassembled mechanical parts, "
                    f"components separated and floating with clear spacing, sequential motion of parts, "
                    f"technical product visualization, kinematic assembly breakdown, "
                    f"{prompt}, cinematic studio lighting, high detail, photorealistic"
                )
                neg_prompt = (
                    "single intact object, fully assembled only, merged fused parts, no separation, "
                    "abstract blobs, extra limbs, text, watermark, low quality, blurry, noisy, deformed"
                )
            elif color_word and has_liquid:
                profile = "color_liquid"
                enhanced_prompt = (
                    f"{color_word} colored liquid, {color_word} water, {prompt}, "
                    f"vibrant {color_word} tint, physically plausible fluid motion, "
                    f"photorealistic, high detail, cinematic"
                )
                neg_prompt = (
                    "clear water, transparent colorless liquid, wrong color, muddy color, "
                    "bad quality, blurry, pixelated, noisy, watermark, text, deformed"
                )
            else:
                if has_motion:
                    profile = "general_motion"
                    guidance_scale = 2.5
                enhanced_prompt = (
                    f"{prompt}, coherent motion, stable geometry, photorealistic, "
                    f"high detail, cinematic lighting, best quality"
                )
                neg_prompt = (
                    "flicker, geometry collapse, morphing artifacts, low quality, blurry, "
                    "pixelated, noisy, watermark, text, deformed"
                )

            logger.info(f"🎛️ Video prompt profile: {profile}")
            logger.info(f"\U0001f3a8 Enhanced prompt: {enhanced_prompt[:160]}...")

            # Shared seeded generator improves identity consistency across frames/stages.
            seed = abs(hash((request_id, prompt))) % (2**31)
            generator = torch.Generator(device="cpu").manual_seed(seed)

            backend_name = "animatelcm/epiCRealism"

            # For engineering exploded requests, enforce temporal intent with a
            # single-subject keyframe + deterministic assembly animation.
            # This avoids multi-car/collage drift from free-form T2V sampling.
            if profile == "engineering_exploded":
                # FIRST: try real engineering libraries (cadquery + trimesh) pipeline.
                lib_frames = self._generate_engineering_exploded_with_libraries(
                    request_id=request_id,
                    prompt=prompt,
                    total_frames=num_frames,
                    width=width,
                    height=height,
                )
                if lib_frames:
                    frames = lib_frames
                    backend_name = "cadquery+trimesh_engineering"
                    logger.info(f"🛠️ Engineering library pipeline applied ({len(frames)} frames total)")
                else:
                    keyframe_prompt = (
                        f"(single supercar only:1.9), "
                        f"(exploded mechanical assembly view:1.8), "
                        f"(parts clearly separated around one chassis:1.8), "
                        f"(centered composition:1.7), (locked camera:1.7), "
                        f"(technical studio lighting:1.4), {prompt}"
                    )
                    neg_prompt = (
                        "two cars, multiple cars, duplicate vehicle, split screen, collage, montage, "
                        "scene cut, camera jump, multi-view layout, intact-only body, merged parts, "
                        "blurry, low quality, text, watermark"
                    )
                    if self.event_bus:
                        self.event_bus.publish("visual.generation.progress", {
                            "request_id": request_id,
                            "progress": 20
                        })
                    key = pipe(
                        prompt=keyframe_prompt,
                        negative_prompt=neg_prompt,
                        num_frames=1,
                        guidance_scale=max(guidance_scale, 3.5),
                        num_inference_steps=max(steps, 10),
                        width=width,
                        height=height,
                        generator=generator,
                    )
                    if self.event_bus:
                        self.event_bus.publish("visual.generation.progress", {
                            "request_id": request_id,
                            "progress": 60
                        })
                    base_frame = key.frames[0][0]
                    frames = self._synthesize_exploded_assembly_frames(base_frame, total_frames=num_frames)
                    logger.info(f"🧩 Deterministic exploded assembly plan applied ({len(frames)} frames total)")
            else:
                output = pipe(
                    prompt=enhanced_prompt,
                    negative_prompt=neg_prompt,
                    num_frames=num_frames,
                    guidance_scale=guidance_scale,
                    num_inference_steps=steps,
                    width=width,
                    height=height,
                    generator=generator,
                )
                frames = output.frames[0]
            
            # Encode final video (MP4 primary, GIF fallback)
            exports_dir = self._get_exports_dir()
            timestamp = int(time.time() * 1000)
            video_path, gif_fallback = self._encode_video_from_frames(
                frames=frames,
                exports_dir=exports_dir,
                stem=f"kingdom_ai_video_{timestamp}",
                fps=12,
            )
            
            logger.info(f"🎬 Video saved: {video_path} ({len(frames)} frames)")
            
            # Convert first frame to QImage for canvas display
            first_frame = frames[0]
            qimage = self._pil_to_qimage(first_frame)
            
            metadata = {
                "backend": backend_name,
                "image_path": str(video_path),
                "video_path": str(video_path),
                "preview_gif_path": str(gif_fallback) if gif_fallback else "",
                "width": width,
                "height": height,
                "num_frames": len(frames),
                "steps": steps,
                "prompt": prompt,
                "request_id": request_id,
                "type": "video"
            }
            
            if self.generation_complete and qimage:
                self.generation_complete.emit(qimage, metadata)
            
            if self.event_bus:
                self.event_bus.publish("visual.generated", {
                    "image_path": str(video_path),
                    "video_path": str(video_path),
                    "preview_gif_path": str(gif_fallback) if gif_fallback else "",
                    "request_id": request_id,
                    "prompt": prompt,
                    "backend": backend_name,
                    "type": "video",
                    "num_frames": len(frames),
                    "width": width,
                    "height": height
                })
                self.event_bus.publish("visual.generation.progress", {
                    "request_id": request_id,
                    "progress": 100,
                    "preview_path": str(video_path)
                })
                
        except Exception as e:
            logger.error(f"❌ Video generation failed: {e}", exc_info=True)
            if self.generation_error:
                self.generation_error.emit(request_id, str(e))
            if self.event_bus:
                self.event_bus.publish("visual.generation.error", {
                    "request_id": request_id,
                    "error": str(e)
                })

    def _synthesize_exploded_assembly_frames(self, base_frame, total_frames: int = 16):
        """Build a full-car exploded assembly sequence from one keyframe.

        Reference behavior target: single object, all parts move, sequential
        assembly (similar to exploded CAD animations).
        """
        from PIL import Image, ImageEnhance, ImageFilter, ImageStat
        import math

        if total_frames < 8:
            total_frames = 8

        base = base_frame.convert("RGBA")
        w, h = base.size

        # Preserve scene context while emphasizing moving parts.
        bg = ImageEnhance.Brightness(base.convert("RGB")).enhance(0.30).convert("RGBA")
        bg = bg.filter(ImageFilter.GaussianBlur(radius=1.2))

        # Force a single-subject region around the center to avoid collage drift.
        # This region is intentionally broad to cover the whole car silhouette.
        ox1, oy1 = int(0.12 * w), int(0.24 * h)
        ox2, oy2 = int(0.88 * w), int(0.78 * h)
        obj_w, obj_h = ox2 - ox1, oy2 - oy1
        center_x = ox1 + obj_w / 2.0
        center_y = oy1 + obj_h / 2.0

        cols, rows = 8, 4  # many moving pieces across full car body
        cell_w = max(8, obj_w // cols)
        cell_h = max(8, obj_h // rows)

        parts = []
        for r in range(rows):
            for c in range(cols):
                x1 = ox1 + c * cell_w
                y1 = oy1 + r * cell_h
                x2 = ox2 if c == cols - 1 else min(ox2, x1 + cell_w)
                y2 = oy2 if r == rows - 1 else min(oy2, y1 + cell_h)
                if x2 - x1 < 6 or y2 - y1 < 6:
                    continue

                tile = base.crop((x1, y1, x2, y2)).convert("RGB")
                # Skip flat background-like tiles.
                stat = ImageStat.Stat(tile)
                variance = sum(stat.var) / 3.0
                if variance < 120.0:
                    continue

                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                vx = (cx - center_x) / max(1.0, obj_w / 2.0)
                vy = (cy - center_y) / max(1.0, obj_h / 2.0)
                mag = math.sqrt(vx * vx + vy * vy)
                if mag < 1e-6:
                    vx, vy, mag = 0.0, -1.0, 1.0
                vx /= mag
                vy /= mag

                # Larger radial offsets for a clearly exploded full-car look.
                radial = 0.18 * w
                dx0 = int(vx * radial * (0.85 + 0.30 * (mag)))
                dy0 = int(vy * radial * (0.70 + 0.35 * (mag)))
                # Slight vertical lift gives technical "floating parts" feel.
                dy0 -= int(0.05 * h)

                # Sequence timing: center core assembles first, outer parts later.
                delay = min(0.55, max(0.0, mag * 0.45))
                parts.append({
                    "bbox": (x1, y1, x2, y2),
                    "ofs": (dx0, dy0),
                    "delay": delay,
                    "z": mag,
                })

        if not parts:
            # Safe fallback to old behavior if segmentation found nothing.
            return [base.convert("RGB")] * total_frames

        # Draw farther parts first, center parts on top.
        parts.sort(key=lambda p: p["z"], reverse=True)

        frames = []
        for i in range(total_frames):
            t = i / max(1, total_frames - 1)
            canvas = bg.copy()

            for part in parts:
                x1, y1, x2, y2 = part["bbox"]
                dx0, dy0 = part["ofs"]
                delay = part["delay"]

                if t <= delay:
                    local = 0.0
                else:
                    local = min(1.0, (t - delay) / max(1e-6, 1.0 - delay))
                # 1.0->0.0 offset over time (exploded -> assembled).
                ease = (1.0 - local) ** 1.5

                dx = int(dx0 * ease)
                dy = int(dy0 * ease)
                piece = base.crop((x1, y1, x2, y2))
                px = max(0, min(w - (x2 - x1), x1 + dx))
                py = max(0, min(h - (y2 - y1), y1 + dy))
                canvas.alpha_composite(piece, (px, py))

            frames.append(canvas.convert("RGB"))

        return frames

    def _compute_radial_explosion_vectors(self, components: list) -> dict:
        """
        SOTA 2026: Radial decomposition for exploded view.
        Compute explosion vectors from assembly centroid to each component.
        Returns unit direction vectors (radial outward + axial); caller applies magnitude.
        """
        if not components:
            return {}
        import numpy as np
        positions = []
        for c in components:
            pos = c.get("position", {}) or {}
            x = float(pos.get("x", 0.0))
            y = float(pos.get("y", 0.0))
            z = float(pos.get("z", 0.0))
            positions.append(np.array([x, y, z], dtype=np.float32))
        center = np.mean(positions, axis=0)
        result = {}
        for i, c in enumerate(components):
            name = str(c.get("name", f"component_{i}")).lower()
            pos = positions[i]
            delta = pos - center
            dist = float(np.linalg.norm(delta))
            if dist < 1e-6:
                vec = np.array([1.0, 0.0, 0.3], dtype=np.float32)
            else:
                vec = delta / dist
            result[name] = (float(vec[0]), float(vec[1]), float(vec[2]))
        return result

    def _generate_engineering_exploded_with_libraries(self, request_id: str, prompt: str, total_frames: int, width: int, height: int):
        """Generate exploded assembly animation via CAD/mesh libraries.

        Uses installed engineering stack first (cadquery + trimesh).
        Returns PIL frames list or None when unavailable.
        """
        try:
            import numpy as np
            import cadquery as cq
            import trimesh
            from PIL import Image, ImageDraw
        except Exception as e:
            logger.info(f"Engineering libs unavailable for CAD path: {e}")
            return None

        if total_frames < 12:
            total_frames = 12

        p = (prompt or "").lower()
        is_supercar = any(k in p for k in ("supercar", "hypercar", "ferrari", "lamborghini", "mclaren"))
        is_track = any(k in p for k in ("track", "race", "racing", "gt3", "f1"))
        body_color = (220, 40, 30)
        if "blue" in p:
            body_color = (44, 112, 230)
        elif "green" in p:
            body_color = (35, 166, 96)
        elif "yellow" in p:
            body_color = (230, 190, 40)
        elif "white" in p:
            body_color = (220, 220, 220)
        elif "black" in p:
            body_color = (65, 65, 70)

        # Prompt-aware parametric assembly built with CAD primitives.
        def _to_mesh(wp):
            shape = wp.val()
            verts, faces = shape.tessellate(0.35)
            v = np.array([[p.x, p.y, p.z] for p in verts], dtype=np.float32)
            f = np.array(faces, dtype=np.int32)
            return trimesh.Trimesh(vertices=v, faces=f, process=False)

        parts = []

        def _add_part(mesh_wp, pos, color, ofs, stg):
            parts.append(
                {
                    "m": _to_mesh(mesh_wp),
                    "p": np.array(pos, dtype=np.float32),
                    "c": color,
                    "ofs": np.array(ofs, dtype=np.float32),
                    "stage": int(stg),
                }
            )

        # ------------------------------------------------------------
        # True text->parametric path: compile prompt via CAD engine.
        # ------------------------------------------------------------
        if self.event_bus:
            self.event_bus.publish("visual.generation.progress", {
                "request_id": request_id,
                "progress": 18,
                "message": "Initializing CAD engine..."
            })
        compiled_components = []
        try:
            from core.cad_mechanical_engineering_engine import get_cad_engine
            cad_engine = get_cad_engine(event_bus=self.event_bus)
            if self.event_bus:
                self.event_bus.publish("visual.generation.progress", {
                    "request_id": request_id,
                    "progress": 22,
                    "message": "CAD engine ready, decomposing object..."
                })
            if self.event_bus:
                self.event_bus.publish("visual.generation.progress", {
                    "request_id": request_id,
                    "progress": 28,
                    "message": "Compiling parametric CAD components..."
                })
            loop = asyncio.new_event_loop()
            try:
                model = loop.run_until_complete(
                    cad_engine.generate_from_text(prompt)
                )
            finally:
                loop.close()
            hierarchy = (model.metadata or {}).get("object_hierarchy", {}) if model else {}
            compiled_components = hierarchy.get("subcomponents", []) if isinstance(hierarchy, dict) else []
            assembly_plan = (model.metadata or {}).get("assembly_plan", {}) if model else {}
            logger.info(f"🧠 CAD compiler produced {len(compiled_components)} components from prompt")
            if self.event_bus:
                self.event_bus.publish("visual.generation.progress", {
                    "request_id": request_id,
                    "progress": 42,
                    "message": f"CAD decomposition complete ({len(compiled_components)} components)"
                })
        except Exception as e:
            logger.warning(f"CAD compiler first attempt failed ({e}), retrying once...")
            try:
                loop2 = asyncio.new_event_loop()
                try:
                    model = loop2.run_until_complete(
                        cad_engine.generate_from_text(prompt)
                    )
                finally:
                    loop2.close()
                hierarchy = (model.metadata or {}).get("object_hierarchy", {}) if model else {}
                compiled_components = hierarchy.get("subcomponents", []) if isinstance(hierarchy, dict) else []
                logger.info(f"🧠 CAD compiler retry succeeded: {len(compiled_components)} components")
            except Exception as retry_err:
                logger.info(f"CAD compiler retry also failed ({retry_err}), using templates")

        if compiled_components:
            # Normalize mm-scale component dimensions into scene units.
            max_dim_mm = 1.0
            for c in compiled_components:
                d = c.get("dimensions", {}) or {}
                for key in ("length", "width", "height", "radius"):
                    try:
                        max_dim_mm = max(max_dim_mm, float(d.get(key, 0.0)))
                    except Exception:
                        pass
            unit = max(180.0, max_dim_mm) / 3.8

            explosion_vectors = (assembly_plan.get("explosion_vectors", {}) or {}) if isinstance(assembly_plan, dict) else {}
            # SOTA 2026: Radial decomposition when explosion_vectors missing - compute from assembly center
            if not explosion_vectors and compiled_components:
                explosion_vectors = self._compute_radial_explosion_vectors(compiled_components)
            design_env = (assembly_plan.get("design_envelope_mm", {}) or {}) if isinstance(assembly_plan, dict) else {}
            if not design_env and isinstance(hierarchy, dict):
                design_env = hierarchy.get("design_envelope_mm", {}) or {}
            env_l = float(design_env.get("length", 0.0) or 0.0)
            env_w = float(design_env.get("width", 0.0) or 0.0)
            env_h = float(design_env.get("height", 0.0) or 0.0)
            if env_l and env_w and env_h:
                logger.info("📐 CAD envelope from brain: LxWxH=%.0fx%.0fx%.0f mm", env_l, env_w, env_h)

            for i, comp in enumerate(compiled_components):
                d = comp.get("dimensions", {}) or {}
                pos = comp.get("position", {}) or {}
                typ = str(comp.get("type", "rectangular")).lower()
                name = str(comp.get("name", f"component_{i}")).lower()

                length = max(0.16, float(d.get("length", d.get("l", 220.0))) / unit)
                width_mm = float(d.get("width", d.get("w", 140.0)))
                height_mm = float(d.get("height", d.get("h", 100.0)))
                width_u = max(0.12, width_mm / unit)
                height_u = max(0.10, height_mm / unit)
                radius_u = max(0.09, float(d.get("radius", d.get("r", 70.0))) / unit)

                px = float(pos.get("x", 0.0)) / unit
                py = float(pos.get("y", 0.0)) / unit
                pz = float(pos.get("z", 0.0)) / unit
                base_pos = (px, py, pz)

                ang = (2.0 * np.pi * i) / max(1, len(compiled_components))
                radial = 2.1 + 0.8 * (i % 3)
                zlift = 1.1 + 0.22 * (i % 4)
                base_ofs = (np.cos(ang) * radial, np.sin(ang) * radial, zlift)
                vec = explosion_vectors.get(name, None)
                if isinstance(vec, (list, tuple)) and len(vec) >= 3:
                    ofs = (float(vec[0]) * radial, float(vec[1]) * radial, float(vec[2]) * zlift)
                else:
                    ofs = base_ofs
                if any(k in name for k in ("chassis", "frame", "platform")):
                    stage = 0
                elif any(k in name for k in ("suspension", "brake", "disc", "hub")):
                    stage = 1
                elif any(k in name for k in ("wheel", "tire", "rim")):
                    stage = 2
                elif any(k in name for k in ("engine", "motor", "gearbox", "radiator")):
                    stage = 3
                elif any(k in name for k in ("body", "shell", "door", "hood", "bumper", "deck", "panel")):
                    stage = 4
                else:
                    stage = 2 + (i % 3)

                color_seed = abs(hash(name)) % 180
                if "wheel" in name or "tire" in name:
                    col = (20, 20, 22)
                elif "body" in name or "shell" in name or "panel" in name or "door" in name:
                    col = body_color
                elif "engine" in name or "motor" in name or "gear" in name:
                    col = (112, 112, 118)
                else:
                    col = (55 + (color_seed // 3), 65 + (color_seed // 4), 75 + (color_seed // 5))

                if typ.startswith("cyl"):
                    mesh_wp = cq.Workplane("YZ").circle(radius_u).extrude(max(0.12, height_u * 0.45))
                elif any(k in name for k in ("body", "shell", "cabin", "cockpit", "fuselage")):
                    mesh_wp = (
                        cq.Workplane("XY")
                        .workplane(offset=0.00).rect(max(0.22, length * 0.98), max(0.22, width_u * 0.90))
                        .workplane(offset=max(0.12, height_u * 0.52)).rect(max(0.18, length * 0.70), max(0.18, width_u * 0.74))
                        .workplane(offset=max(0.20, height_u * 0.98)).rect(max(0.12, length * 0.34), max(0.12, width_u * 0.46))
                        .loft(combine=True)
                    )
                elif any(k in name for k in ("hood", "deck", "bumper", "facade", "cover")):
                    mesh_wp = (
                        cq.Workplane("XY")
                        .workplane(offset=0.00).rect(max(0.16, length), max(0.16, width_u))
                        .workplane(offset=max(0.08, height_u * 0.55)).rect(max(0.12, length * 0.70), max(0.12, width_u * 0.82))
                        .loft(combine=True)
                    )
                elif any(k in name for k in ("chassis", "frame", "platform", "foundation", "base", "outsole", "hull")):
                    mesh_wp = (
                        cq.Workplane("XY")
                        .box(max(0.18, length), max(0.18, width_u), max(0.10, height_u * 0.7))
                        .edges("|Z").fillet(max(0.02, min(length, width_u) * 0.05))
                    )
                elif any(k in name for k in ("engine", "motor", "gearbox", "transmission", "reactor", "battery")):
                    mesh_wp = (
                        cq.Workplane("XY")
                        .box(max(0.12, length * 0.78), max(0.12, width_u * 0.78), max(0.10, height_u * 0.72))
                        .faces(">Z").workplane().box(max(0.08, length * 0.42), max(0.08, width_u * 0.42), max(0.05, height_u * 0.25), combine=True)
                    )
                elif any(k in name for k in ("door", "panel", "wing", "aileron", "stabilizer",
                                               "petal", "leaf", "blade", "tongue")):
                    mesh_wp = cq.Workplane("XY").box(max(0.14, length), max(0.06, width_u * 0.22), max(0.10, height_u))
                elif any(k in name for k in ("head", "skull", "snout", "beak")):
                    mesh_wp = (
                        cq.Workplane("XY")
                        .workplane(offset=0.00).rect(max(0.10, length * 0.90), max(0.10, width_u * 0.90))
                        .workplane(offset=max(0.08, height_u * 0.90)).rect(max(0.08, length * 0.60), max(0.08, width_u * 0.60))
                        .loft(combine=True)
                    )
                elif any(k in name for k in ("leg", "arm", "limb", "thigh", "shin", "forearm", "branch", "trunk", "stem")):
                    mesh_wp = cq.Workplane("XY").cylinder(max(0.10, height_u), max(0.04, radius_u * 0.6))
                else:
                    mesh_wp = cq.Workplane("XY").box(length, width_u, height_u)

                _add_part(mesh_wp, base_pos, col, ofs, stage)

        if not parts:
            logger.info("⚠️ CAD compiler produced no components; building generic assembly fallback")
            colors_cycle = [
                (60, 120, 200), (200, 60, 60), (60, 200, 120), (200, 180, 60),
                (140, 60, 200), (200, 120, 60), (60, 200, 200), (180, 180, 180),
            ]
            _add_part(cq.Workplane("XY").box(3.0, 2.0, 0.4), (0.0, 0.0, 0.0), (50, 55, 65), (0.0, 0.0, -2.0), 0)
            _add_part(cq.Workplane("XY").box(2.4, 1.6, 1.2), (0.0, 0.0, 0.8), colors_cycle[0], (0.0, 0.0, 2.5), 1)
            _add_part(cq.Workplane("XY").box(1.8, 1.2, 0.8), (0.0, 0.0, 1.8), colors_cycle[1], (0.0, 0.0, 3.0), 2)
            _add_part(cq.Workplane("XY").box(1.0, 0.8, 0.5), (0.0, 0.0, 2.5), colors_cycle[2], (0.0, 0.0, 3.5), 3)
            _add_part(cq.Workplane("XY").cylinder(0.3, 0.5), (0.0, 0.0, 3.1), colors_cycle[3], (0.0, 0.0, 4.0), 4)
            _add_part(cq.Workplane("XY").box(0.6, 1.2, 0.5), (0.0, 1.2, 1.0), colors_cycle[4], (0.0, 2.0, 1.0), 3)
            _add_part(cq.Workplane("XY").box(0.6, 1.2, 0.5), (0.0, -1.2, 1.0), colors_cycle[5], (0.0, -2.0, 1.0), 3)
            _add_part(cq.Workplane("XY").box(0.5, 0.6, 0.3), (1.2, 0.0, 1.4), colors_cycle[6], (2.0, 0.0, 0.5), 2)

        # Camera projection with auto-framing to avoid tiny renders.
        yaw, pitch = np.deg2rad(-28.0), np.deg2rad(16.0)
        cy, sy = np.cos(yaw), np.sin(yaw)
        cp, sp = np.cos(pitch), np.sin(pitch)
        rot = np.array(
            [[cy, sy * sp, sy * cp], [0, cp, -sp], [-sy, cy * sp, cy * cp]],
            dtype=np.float32,
        )
        # Estimate extents over assembled and exploded states.
        x_abs_max = 1.0
        y_abs_max = 1.0
        z_min = 0.0
        for part in parts:
            pv = np.asarray(part["m"].vertices, dtype=np.float32)
            for alpha in (0.0, 1.0):
                pos = part["p"] + part["ofs"] * alpha
                v_cam = (pv + pos) @ rot.T
                x_abs_max = max(x_abs_max, float(np.max(np.abs(v_cam[:, 0]))))
                y_abs_max = max(y_abs_max, float(np.max(np.abs(v_cam[:, 1]))))
                z_min = min(z_min, float(np.min(v_cam[:, 2])))

        cam_z = max(6.8, (-z_min) + 2.0)
        scale_x = (width * 0.44) * cam_z / max(1e-5, x_abs_max)
        scale_y = (height * 0.31) * cam_z / max(1e-5, y_abs_max)
        scale = max(min(width, height) * 0.9, min(scale_x, scale_y))
        cx, cy2 = width * 0.5, height * 0.62
        logger.info("🎥 Auto-frame extents: x=%.2f y=%.2f cam_z=%.2f scale=%.2f", x_abs_max, y_abs_max, cam_z, scale)

        light_dir = np.array([0.45, -0.35, 0.82], dtype=np.float32)
        light_dir /= max(1e-6, float(np.linalg.norm(light_dir)))

        # ── SOTA 2026: OpenCV + ThreadPoolExecutor parallel rendering ──
        try:
            import cv2
            _use_cv2 = True
        except ImportError:
            _use_cv2 = False
            logger.info("cv2 unavailable; PIL fallback (slower)")

        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Pre-serialize mesh data once (avoids repeated trimesh→numpy per frame)
        render_parts = []
        for part in parts:
            render_parts.append({
                "v": np.asarray(part["m"].vertices, dtype=np.float32),
                "f": np.asarray(part["m"].faces, dtype=np.int32),
                "p": np.array(part["p"], dtype=np.float32),
                "c": tuple(int(c) for c in part["c"]),
                "ofs": np.array(part["ofs"], dtype=np.float32),
                "stage": int(part["stage"]),
            })

        bg_color = (12, 14, 18)
        shadow_center = (int(width * 0.5), int(height * 0.65))
        shadow_axes = (int(width * 0.24), int(height * 0.07))
        shadow_rect = [int(width * 0.26), int(height * 0.58),
                       int(width * 0.74), int(height * 0.72)]

        def _render_one_frame(fi):
            """Thread-safe single-frame renderer; numpy/cv2 release GIL."""
            t = fi / max(1, total_frames - 1)

            if _use_cv2:
                frame_arr = np.full((height, width, 3), bg_color, dtype=np.uint8)
                cv2.ellipse(frame_arr, shadow_center, shadow_axes,
                            0, 0, 360, (10, 10, 12), -1)
            else:
                pil_img = Image.new("RGB", (width, height), bg_color)
                pil_draw = ImageDraw.Draw(pil_img)
                pil_draw.ellipse(shadow_rect, fill=(10, 10, 12),
                                 outline=(14, 14, 18))

            draw_items = []
            for rp in render_parts:
                st = min(0.88, float(rp["stage"]) / 6.0)
                if t < 0.45:
                    build_t = t / 0.45
                    if build_t <= st:
                        continue
                    local = min(1.0, (build_t - st) / max(1e-6, 1.0 - st))
                    settle = (1.0 - local) ** 1.4
                    pos = rp["p"] + rp["ofs"] * 0.16 * settle
                else:
                    explode_t = min(1.0, (t - 0.45) / 0.55)
                    explode_ease = explode_t ** 1.18
                    pos = rp["p"] + rp["ofs"] * explode_ease

                v = rp["v"] + pos
                v_cam = v @ rot.T
                z_buf = v_cam[:, 2] + cam_z
                if not np.any(z_buf > 0.2):
                    continue
                x2d = cx + scale * (v_cam[:, 0] / z_buf)
                y2d = cy2 - scale * (v_cam[:, 1] / z_buf)

                f = rp["f"]
                if len(f) == 0:
                    continue
                # Vectorized normals + lighting (single numpy call per part)
                a_v = v_cam[f[:, 0]]; b_v = v_cam[f[:, 1]]; c_v = v_cam[f[:, 2]]
                normals = np.cross(b_v - a_v, c_v - a_v)
                norms = np.linalg.norm(normals, axis=1, keepdims=True)
                norms = np.maximum(norms, 1e-6)
                normals /= norms
                intensities = 0.30 + 0.70 * np.clip(
                    np.abs(normals @ light_dir), 0.0, 1.0)
                pc = np.array(rp["c"], dtype=np.float32)
                colors_f = np.clip(
                    np.outer(intensities, pc), 0, 255).astype(np.int32)
                avgz_all = (z_buf[f[:, 0]] + z_buf[f[:, 1]] + z_buf[f[:, 2]]) / 3.0
                x0_f = x2d[f[:, 0]]; x1_f = x2d[f[:, 1]]; x2_f = x2d[f[:, 2]]
                y0_f = y2d[f[:, 0]]; y1_f = y2d[f[:, 1]]; y2_f = y2d[f[:, 2]]
                x0l, x1l, x2l = x0_f.tolist(), x1_f.tolist(), x2_f.tolist()
                y0l, y1l, y2l = y0_f.tolist(), y1_f.tolist(), y2_f.tolist()
                azl = avgz_all.tolist()
                cl = [tuple(row) for row in colors_f.tolist()]
                draw_items.extend(
                    (az, [(xa, ya), (xb, yb), (xc, yc)], c)
                    for az, xa, ya, xb, yb, xc, yc, c
                    in zip(azl, x0l, y0l, x1l, y1l, x2l, y2l, cl)
                )

            draw_items.sort(key=lambda it: it[0], reverse=True)

            if _use_cv2:
                for _z, pts, col in draw_items:
                    tri = np.array(pts, dtype=np.int32)
                    cv2.fillPoly(frame_arr, [tri], col)
                    cv2.polylines(frame_arr, [tri], True, (8, 220, 255), 1)
                return fi, Image.fromarray(frame_arr)
            else:
                for _z, pts, col in draw_items:
                    pil_draw.polygon(pts, fill=col, outline=(0, 0, 0))
                    pil_draw.line([pts[0], pts[1], pts[2], pts[0]],
                                  fill=(8, 220, 255), width=1)
                return fi, pil_img

        max_workers = min(os.cpu_count() or 4, 6)
        frames_dict = {}
        render_start = time.monotonic()
        exports_dir = self._get_exports_dir()

        logger.info("🚀 Engineering render: %d frames @ %dx%d, %d workers, cv2=%s",
                     total_frames, width, height, max_workers, _use_cv2)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_render_one_frame, fi): fi
                       for fi in range(total_frames)}
            completed = 0
            for future in as_completed(futures):
                try:
                    fi, img = future.result()
                except Exception as exc:
                    logger.warning("Frame %d render error: %s",
                                   futures[future], exc)
                    continue
                frames_dict[fi] = img
                completed += 1

                if self.event_bus:
                    prog = 20 + int((completed / total_frames) * 75)
                    payload = {"request_id": request_id,
                               "progress": min(98, prog)}
                    preview_interval = max(1, total_frames // 18)
                    if completed % preview_interval == 0 or \
                       completed == total_frames:
                        try:
                            preview_path = (exports_dir /
                                f"kingdom_preview_{request_id}_{fi:03d}.png")
                            img.save(preview_path)
                            payload["preview_path"] = str(preview_path)
                        except Exception:
                            pass
                    self.event_bus.publish(
                        "visual.generation.progress", payload)

                if completed == 1:
                    elapsed_f0 = time.monotonic() - render_start
                    logger.info(
                        "🎥 First frame in %.2fs — est. total: %.1fs "
                        "(%d workers)",
                        elapsed_f0,
                        elapsed_f0 * total_frames / max_workers,
                        max_workers)

        elapsed_total = time.monotonic() - render_start
        logger.info("🎥 Render done: %d frames in %.1fs (%.1f effective fps)",
                     len(frames_dict), elapsed_total,
                     len(frames_dict) / max(0.01, elapsed_total))

        frames = [frames_dict[i] for i in sorted(frames_dict.keys())]
        return frames
    
    def _generate_with_ollama(self, request_id: str, prompt: str, config: Optional[GenerationConfig] = None):
        """Generate using Ollama backend."""
        logger.info(f"?? Using Ollama backend: {prompt[:50]}...")
        
        try:
            import ollama
            
            # Ollama image generation
            response = ollama.generate(
                model="llava",
                prompt=f"Generate an image: {prompt}",
                stream=False
            )
            
            # Note: Ollama text generation - for images, may need different approach
            # This is a placeholder - actual implementation depends on Ollama image models
            logger.warning("Ollama image generation not fully implemented")
            self._generate_placeholder(request_id, prompt, config)
            
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            self._generate_placeholder(request_id, prompt, config)
    
    def _generate_placeholder(self, request_id: str, prompt: str, config: Optional[GenerationConfig] = None):
        """Generate placeholder image when backends unavailable."""
        logger.info(f"?? Generating placeholder: {prompt[:50]}...")
        
        if not HAS_PYQT6:
            return
        
        width = config.width if config else 1024
        height = config.height if config else 576
        
        # Create placeholder image
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(QColor(52, 152, 219))  # Blue background
        
        # Draw text
        painter = QPainter(image)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        text = f"?? {prompt}\n\n?? Placeholder - Backends unavailable"
        painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        
        # Save placeholder — with fallback to temp dir for WinError 1920
        exports_dir = self._get_exports_dir()
        timestamp = int(time.time() * 1000)
        image_path = exports_dir / f"kingdom_ai_placeholder_{timestamp}.png"
        image.save(str(image_path))
        
        metadata = {
            "backend": "fallback",
            "image_path": str(image_path),
            "width": width,
            "height": height,
            "prompt": prompt,
            "request_id": request_id,
            "is_fallback": True,
            "warning": "No image generation backend available — install diffusers or enable Ollama vision"
        }
        
        if self.generation_complete:
            self.generation_complete.emit(image, metadata)
        
        if self.event_bus:
            self.event_bus.publish("visual.generated", {
                "image_path": str(image_path),
                "request_id": request_id,
                "prompt": prompt,
                "backend": "placeholder"
            })
    
    def _generate_with_redis_service(self, request_id: str, prompt: str, config: Optional[GenerationConfig] = None):
        """Generate image using Redis Creation Engine Service (isolated environment)."""
        if not self._redis_client:
            logger.error("❌ Redis client not available")
            return
        
        try:
            import json
            try:
                from core.redis_channels import ImageChannels
                request_channel = ImageChannels.REQUEST
                response_channel = ImageChannels.RESPONSE
                progress_channel = ImageChannels.PROGRESS
            except Exception:
                request_channel = 'creation.request'
                response_channel = 'creation.response'
                progress_channel = 'creation.progress'
            
            logger.info(f"🎨 Publishing creation request to Redis service: {prompt[:50]}...")
            
            # Publish request to creation service
            request_data = {
                'request_id': request_id,
                'prompt': prompt,
                'mode': 'image',
                'backend': 'auto',
                'width': config.width if config else 1024,
                'height': config.height if config else 576,
                'steps': config.steps if config else 25,
                'guidance_scale': config.guidance_scale if config else 7.5,
                'config': {
                    'width': config.width if config else 1024,
                    'height': config.height if config else 576,
                    'steps': config.steps if config else 25,
                    'guidance_scale': config.guidance_scale if config else 7.5,
                    'backend': 'auto',
                }
            }
            
            self._redis_client.publish(request_channel, json.dumps(request_data))
            logger.info(f"✅ Request published to Redis - waiting for isolated env to respond")
            
            # Subscribe to response/progress channels
            def listen_for_response():
                pubsub = self._redis_client.pubsub()
                pubsub.subscribe(response_channel, progress_channel)
                
                for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            data = json.loads(message['data'])
                            msg_request_id = data.get('request_id')
                            
                            if msg_request_id != request_id:
                                continue  # Not our request
                            
                            channel = message['channel']
                            
                            if channel == progress_channel:
                                progress = data.get('progress', 0)
                                logger.info(f"📊 Progress: {progress}%")
                                if self.generation_progress:
                                    self.generation_progress.emit(request_id, progress, None)
                                if self.event_bus:
                                    self.event_bus.publish("creation.progress", data)
                            
                            elif channel == response_channel:
                                status = data.get('status')
                                if status == 'complete':
                                    image_path = data.get('image_path')
                                    logger.info(f"✅ Image generated by isolated env: {image_path}")
                                    
                                    # Load image and emit
                                    from PIL import Image
                                    pil_image = Image.open(image_path)
                                    qimage = self._pil_to_qimage(pil_image)
                                    
                                    metadata = {
                                        "backend": "redis_creation_service",
                                        "image_path": image_path,
                                        "width": data.get('width'),
                                        "height": data.get('height'),
                                        "prompt": prompt,
                                        "request_id": request_id
                                    }
                                    
                                    if self.generation_complete:
                                        self.generation_complete.emit(qimage, metadata)
                                    
                                    if self.event_bus:
                                        self.event_bus.publish("visual.generated", {
                                            "image_path": image_path,
                                            "request_id": request_id,
                                            "prompt": prompt,
                                            "backend": "redis_creation_service"
                                        })
                                        self.event_bus.publish("creation.response", data)
                                    
                                    pubsub.close()
                                    break
                                    
                                elif status == 'error':
                                    error = data.get('error', 'Unknown error')
                                    logger.error(f"❌ Generation error: {error}")
                                    if self.generation_error:
                                        self.generation_error.emit(request_id, error)
                                    if self.event_bus:
                                        self.event_bus.publish("creation.response", data)
                                    pubsub.close()
                                    break
                                    
                        except Exception as e:
                            logger.error(f"❌ Error processing message: {e}")
            
            # Start listener in thread with timeout
            from threading import Thread
            listener_thread = Thread(target=listen_for_response, daemon=True)
            listener_thread.start()
            
            pass
            
        except Exception as e:
            logger.error(f"❌ Redis service generation failed: {e}", exc_info=True)
            if self.generation_error:
                self.generation_error.emit(request_id, str(e))
    
    def _latents_to_preview(self, latents, pipe):
        """Convert latents to preview PIL Image."""
        try:
            import torch
            from PIL import Image
            import numpy as np
            
            if latents is None or pipe is None or not hasattr(pipe, 'vae'):
                return None
            
            # Decode latents to image
            with torch.no_grad():
                # Scale latents
                latents = 1 / pipe.vae.config.scaling_factor * latents
                # Decode
                image = pipe.vae.decode(latents[:1]).sample
                # Normalize
                image = (image / 2 + 0.5).clamp(0, 1)
                # Convert to numpy
                image = image.cpu().permute(0, 2, 3, 1).numpy()[0]
                image = (image * 255).astype(np.uint8)
                # Convert to PIL
                preview_image = Image.fromarray(image)
                return preview_image
        except Exception as e:
            logger.debug(f"Preview generation error: {e}")
            return None
    
    def _pil_to_qimage(self, pil_image):
        """Convert PIL Image to QImage with proper format handling."""
        if not HAS_PYQT6:
            return None
        
        try:
            import numpy as np
            
            # Convert PIL to numpy array
            arr = np.array(pil_image)
            
            # Ensure contiguous array
            if not arr.flags['C_CONTIGUOUS']:
                arr = np.ascontiguousarray(arr)
            
            if len(arr.shape) == 3:
                h, w, ch = arr.shape
                bytes_per_line = ch * w
                
                # Create QImage from array data
                qimage = QImage(arr.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                
                # Make copy to ensure data lifetime
                qimage = qimage.copy()
                
                # Convert to RGB32 for safer handling (PyQt6 128MB limit)
                if not qimage.isNull():
                    qimage = qimage.convertToFormat(QImage.Format.Format_RGB32)
                
                return qimage
        except Exception as e:
            logger.error(f"PIL to QImage conversion error: {e}")
            return None
        
        return None

    def _encode_video_from_frames(self, frames, exports_dir: Path, stem: str, fps: int = 12):
        """Encode PIL frames to high-quality MP4, with GIF fallback."""
        if not frames:
            raise ValueError("No frames provided for video encoding")

        video_path = exports_dir / f"{stem}.mp4"
        gif_fallback_path = exports_dir / f"{stem}.gif"

        # Preferred path: OpenCV MP4 encoding.
        try:
            import cv2
            import numpy as np

            first = np.asarray(frames[0].convert("RGB"), dtype=np.uint8)
            h, w = first.shape[:2]
            if w % 2 != 0:
                w -= 1
            if h % 2 != 0:
                h -= 1
            if w < 2 or h < 2:
                raise RuntimeError(f"Invalid frame size for encoder: {w}x{h}")

            writers = []
            for codec in ("avc1", "H264", "mp4v"):
                fourcc = cv2.VideoWriter_fourcc(*codec)
                writer = cv2.VideoWriter(str(video_path), fourcc, float(max(1, fps)), (w, h))
                if writer is not None and writer.isOpened():
                    writers.append((codec, writer))
                    break
                try:
                    writer.release()
                except Exception:
                    pass

            if not writers:
                raise RuntimeError("Could not open MP4 VideoWriter with any supported codec")

            codec_name, out = writers[0]
            try:
                for fr in frames:
                    arr = np.asarray(fr.convert("RGB"), dtype=np.uint8)
                    if arr.shape[1] != w or arr.shape[0] != h:
                        arr = cv2.resize(arr, (w, h), interpolation=cv2.INTER_CUBIC)
                    out.write(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
            finally:
                out.release()

            if video_path.exists() and video_path.stat().st_size > 0:
                logger.info(f"🎬 MP4 encoded ({codec_name}): {video_path}")
                return str(video_path), ""
            raise RuntimeError("MP4 file not written after VideoWriter release")
        except Exception as e:
            logger.warning(f"MP4 encoding failed, trying GIF fallback: {e}")

        # Fallback path: animated GIF so pipeline still completes.
        try:
            first = frames[0]
            duration_ms = max(50, int(1000 / max(1, fps)))
            first.save(
                str(gif_fallback_path),
                save_all=True,
                append_images=frames[1:],
                optimize=False,
                duration=duration_ms,
                loop=0,
            )
            logger.warning(f"⚠️ Using GIF fallback video artifact: {gif_fallback_path}")
            return str(gif_fallback_path), str(gif_fallback_path)
        except Exception as e:
            raise RuntimeError(f"Both MP4 and GIF encoding failed: {e}") from e
    
    def restore_video(self, request_id: str, video_path: str, config: Optional[Dict[str, Any]] = None):
        """Restore video using AI Video Restorer pipeline."""
        if not HAS_VIDEO_RESTORER:
            logger.error("❌ AI Video Restorer not available")
            if self.generation_error:
                self.generation_error.emit(request_id, "AI Video Restorer not installed")
            return
        
        try:
            logger.info(f"🎬 Starting video restoration: {video_path}")
            
            # Emit started signal
            if self.generation_started:
                self.generation_started.emit(request_id)
            
            # Create pipeline config
            pipeline_config = PipelineConfig()
            if config:
                # Apply custom config
                pipeline_config.colorize_method = config.get('colorize_method', 'ddcolor')
                pipeline_config.colorize_strength = config.get('colorize_strength', 1.0)
                pipeline_config.enable_colorize = config.get('enable_colorize', True)
                pipeline_config.upscale_factor = config.get('upscale_factor', 4)
                pipeline_config.enable_upscale = config.get('enable_upscale', True)
                pipeline_config.enable_face_enhance = config.get('enable_face_enhance', True)
                pipeline_config.enable_detect = config.get('enable_detect', True)
                pipeline_config.target_width = config.get('target_width', 3840)
                pipeline_config.target_height = config.get('target_height', 2160)
            
            # Create restoration pipeline
            pipeline = VideoRestorationPipeline(pipeline_config)
            
            # Set up progress callback
            def progress_callback(stage: str, progress: int, frame_idx: int = 0):
                logger.info(f"📊 {stage}: {progress}% (frame {frame_idx})")
                if self.generation_progress:
                    self.generation_progress.emit(request_id, progress, None)
                if self.event_bus:
                    self.event_bus.publish("visual.restoration.progress", {
                        "request_id": request_id,
                        "stage": stage,
                        "progress": progress,
                        "frame": frame_idx
                    })
            
            # Process video
            output_path = pipeline.process_video(
                video_path,
                progress_callback=progress_callback
            )
            
            logger.info(f"✅ Video restoration complete: {output_path}")
            
            # Emit completion with video path
            metadata = {
                'type': 'video_restoration',
                'input_path': video_path,
                'output_path': str(output_path),
                'config': config or {},
                'backend': 'ai_video_restorer'
            }
            
            if self.generation_complete:
                # For video, we emit the path as metadata
                self.generation_complete.emit(None, metadata)
            
            if self.event_bus:
                self.event_bus.publish("visual.restoration.complete", {
                    "request_id": request_id,
                    "output_path": str(output_path),
                    "metadata": metadata
                })
            
        except Exception as e:
            logger.error(f"❌ Video restoration failed: {e}", exc_info=True)
            if self.generation_error:
                self.generation_error.emit(request_id, str(e))
            if self.event_bus:
                self.event_bus.publish("visual.restoration.error", {
                    "request_id": request_id,
                    "error": str(e)
                })

class VisualCreationCanvas(QWidget if HAS_PYQT6 else object):
    """
    UNIFIED CREATION CANVAS - Multi-Engine Orchestration Hub
    =========================================================
    
    This widget is the MAIN ENTRY POINT for all creation requests.
    It intelligently routes requests to multiple engines and combines outputs.
    
    FEATURES:
    - Simple requests → Single engine (image, video, map)
    - Complex requests → Multi-engine pipeline (medical + animation + video)
    - Automatic engine selection based on request analysis
    - Real-time progress updates from all engines
    - Unified output display (images, videos, 3D models)
    """
    """Visual Creation Canvas widget with full SOTA 2026 features."""
    if HAS_PYQT6:
        image_generated = pyqtSignal(object, dict)  # image (QImage), metadata
        generation_requested = pyqtSignal(str, str, object)  # request_id, prompt, config
        canvas_toggled = pyqtSignal(bool)  # visibility changed
    
    def __init__(self, event_bus=None, parent=None):
        if HAS_PYQT6:
            super().__init__(parent)
        self.event_bus = event_bus
        self._worker = None
        self._worker_thread = None
        self._generation_config = GenerationConfig()
        self._last_displayed_image = None
        self._booktok_aggregator = None
        
        # SOTA 2026 MULTI-ENGINE ORCHESTRATION
        self._orchestrator = None  # Lazy-loaded on first complex request
        self._use_orchestrator = True  # Enable multi-engine workflows
        
        if HAS_PYQT6:
            self._setup_ui()
            self._setup_worker()
            self._connect_event_bus()
            self._init_booktok()
    
    def _setup_ui(self):
        """Setup UI with SOTA 2026 video playback support."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # SOTA 2026: Use QStackedWidget to switch between image display and video player
        self._display_stack = QStackedWidget()
        self._display_stack.setMinimumSize(800, 600)
        
        # Index 0: Image label for static images
        self.image_label = QLabel("🎨 Visual Creation Canvas")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 2px solid #007BFF;
                border-radius: 8px;
                color: white;
                font-size: 16px;
            }
        """)
        self._display_stack.addWidget(self.image_label)  # Index 0
        
        # Index 1: SOTA 2026 RealTimeVideoPlayer for continuous video playback
        self._video_player = None
        if HAS_VIDEO_PLAYER and RealTimeVideoPlayer:
            try:
                self._video_player = RealTimeVideoPlayer(parent=self, event_bus=self.event_bus)
                self._video_player.playback_finished.connect(self._on_video_playback_finished)
                self._video_player.error_occurred.connect(self._on_video_error)
                self._display_stack.addWidget(self._video_player)  # Index 1
                logger.info("✅ SOTA 2026 RealTimeVideoPlayer initialized for continuous video playback")
            except Exception as e:
                logger.warning(f"⚠️ RealTimeVideoPlayer init failed, using thumbnail fallback: {e}")
                self._video_player = None
        else:
            logger.info("ℹ️ RealTimeVideoPlayer not available, using static thumbnail display")
        
        layout.addWidget(self._display_stack)
        
        # SOTA 2026: Add Video Editing Control Panel
        self._control_panel = self._create_control_panel()
        layout.addWidget(self._control_panel)
        
        # Store reference for video path
        self._last_generated_video = None
        self._last_uploaded_video = None
        self._current_video_path = None
        self._video_clips = []  # List of clips on timeline
        self._cut_markers = []  # Cut points
        self._playback_position = 0.0  # Current playback position in seconds
        self._is_playing = False
    
    def _create_control_panel(self) -> QWidget:
        """Create SOTA 2026 video editing control panel."""
        from PyQt6.QtWidgets import QGroupBox, QGridLayout, QSlider, QComboBox, QFileDialog
        
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel("🎬 Video Editor Controls (SOTA 2026)")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #ff6b6b; padding: 5px;")
        layout.addWidget(title)
        
        # === TIMELINE SCRUBBER ===
        timeline_group = QGroupBox("📽️ Timeline")
        timeline_layout = QVBoxLayout()
        
        # Timecode display
        timecode_layout = QHBoxLayout()
        self._timecode_label = QLabel("00:00:00:00")
        self._timecode_label.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        self._timecode_label.setStyleSheet("color: #00ff00; padding: 3px;")
        timecode_layout.addWidget(self._timecode_label)
        timecode_layout.addStretch()
        
        self._duration_label = QLabel("Duration: 00:00:00")
        self._duration_label.setStyleSheet("color: #888; font-size: 10px;")
        timecode_layout.addWidget(self._duration_label)
        timeline_layout.addLayout(timecode_layout)
        
        # Timeline scrubber
        self._timeline_scrubber = QSlider(Qt.Orientation.Horizontal)
        self._timeline_scrubber.setMinimum(0)
        self._timeline_scrubber.setMaximum(10000)
        self._timeline_scrubber.valueChanged.connect(self._on_timeline_scrub)
        self._timeline_scrubber.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #1a1a1a;
                height: 8px;
                border-radius: 4px;
                border: 1px solid #3d3d3d;
            }
            QSlider::handle:horizontal {
                background: #ff6b6b;
                width: 18px;
                height: 18px;
                margin: -5px 0;
                border-radius: 9px;
                border: 2px solid #fff;
            }
            QSlider::handle:horizontal:hover {
                background: #ff5252;
            }
        """)
        timeline_layout.addWidget(self._timeline_scrubber)
        
        # Cut markers display
        self._markers_label = QLabel("Cuts: None")
        self._markers_label.setStyleSheet("color: #888; font-size: 9px; padding: 2px;")
        timeline_layout.addWidget(self._markers_label)
        
        timeline_group.setLayout(timeline_layout)
        layout.addWidget(timeline_group)
        
        # === PLAYBACK CONTROLS ===
        playback_layout = QHBoxLayout()
        
        self._play_btn = QPushButton("▶ Play")
        self._play_btn.clicked.connect(self._toggle_playback)
        self._play_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px;")
        playback_layout.addWidget(self._play_btn)
        
        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.clicked.connect(self._stop_playback)
        playback_layout.addWidget(self._stop_btn)
        
        self._prev_frame_btn = QPushButton("⏮ Prev")
        self._prev_frame_btn.clicked.connect(self._prev_frame)
        playback_layout.addWidget(self._prev_frame_btn)
        
        self._next_frame_btn = QPushButton("⏭ Next")
        self._next_frame_btn.clicked.connect(self._next_frame)
        playback_layout.addWidget(self._next_frame_btn)
        
        playback_layout.addStretch()
        layout.addLayout(playback_layout)
        
        # === EDITING TOOLS ===
        tools_grid = QGridLayout()
        
        # Row 1: Cut and Trim
        self._cut_btn = QPushButton("✂️ Cut Here")
        self._cut_btn.clicked.connect(self._cut_at_playhead)
        self._cut_btn.setToolTip("Cut video at current playhead position (Voice: 'cut here')")
        self._cut_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        tools_grid.addWidget(self._cut_btn, 0, 0)
        
        self._trim_btn = QPushButton("✂️ Trim")
        self._trim_btn.clicked.connect(self._trim_selection)
        self._trim_btn.setToolTip("Trim selected region (Voice: 'trim')")
        tools_grid.addWidget(self._trim_btn, 0, 1)
        
        self._split_btn = QPushButton("⚡ Split")
        self._split_btn.clicked.connect(self._split_at_playhead)
        self._split_btn.setToolTip("Split clip at playhead")
        tools_grid.addWidget(self._split_btn, 0, 2)
        
        # Row 2: Save and Export
        self._save_btn = QPushButton("💾 Save")
        self._save_btn.clicked.connect(self._save_project)
        self._save_btn.setToolTip("Save project (Voice: 'save')")
        self._save_btn.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        tools_grid.addWidget(self._save_btn, 1, 0)
        
        self._export_btn = QPushButton("🎬 Export")
        self._export_btn.clicked.connect(self._export_video)
        self._export_btn.setToolTip("Export final video (Voice: 'export')")
        self._export_btn.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        tools_grid.addWidget(self._export_btn, 1, 1)
        
        self._undo_btn = QPushButton("↶ Undo")
        self._undo_btn.clicked.connect(self._undo)
        self._undo_btn.setToolTip("Undo last action (Ctrl+Z)")
        tools_grid.addWidget(self._undo_btn, 1, 2)
        
        layout.addLayout(tools_grid)
        
        # === VOICE COMMAND STATUS ===
        self._voice_status = QLabel("🎤 Voice Commands: Ready (say 'cut here', 'save', 'trim', 'export')")
        self._voice_status.setStyleSheet("color: #00ff00; font-size: 10px; padding: 5px; background: #1a1a1a; border-radius: 4px;")
        layout.addWidget(self._voice_status)
        
        # Initially hide control panel until video is loaded
        panel.setVisible(False)
        
        return panel
    
    def _setup_worker(self):
        """Setup worker thread with proper lifecycle management."""
        if not HAS_PYQT6:
            return
        
        self._worker_thread = QThread()
        self._worker = ImageGenerationWorker(self.event_bus)
        self._worker.moveToThread(self._worker_thread)
        
        # Connect signals
        if hasattr(self._worker, 'generation_started'):
            self._worker.generation_started.connect(self._on_generation_started)
        if hasattr(self._worker, 'generation_complete'):
            self._worker.generation_complete.connect(self._on_generation_complete)
        if hasattr(self._worker, 'generation_progress'):
            self._worker.generation_progress.connect(self._on_generation_progress)
        if hasattr(self._worker, 'generation_error'):
            self._worker.generation_error.connect(self._on_generation_error)
        
        # CRITICAL: Do NOT auto-delete thread/worker to prevent "wrapped C/C++ object deleted" errors
        # Keep them alive for reuse
        
        # Start thread with delay
        QTimer.singleShot(3000, self._start_worker_thread)
        logger.info("? VisualCreationCanvas: Worker thread scheduled to start in 3s (generation requests before 3s may queue)")
    
    def _start_worker_thread(self):
        """Start worker thread."""
        if HAS_PYQT6 and self._worker_thread and not self._worker_thread.isRunning():
            self._worker_thread.start()
            logger.info("? VisualCreationCanvas: Worker thread STARTED (image generation ready). Backend status was already emitted by worker at init; check logs for diffusers=True/False.")
    
    def _init_booktok(self):
        """Initialize BookTok Context Aggregator."""
        try:
            from core.booktok_aggregator import BookTokAggregator
            self._booktok_aggregator = BookTokAggregator(event_bus=self.event_bus)
            logger.info("?? BookTok Context Aggregator initialized in Visual Canvas")
        except Exception as e:
            logger.debug(f"BookTok not available: {e}")
            self._booktok_aggregator = None
    
    def _connect_event_bus(self):
        """Connect to EventBus with canonical events + BookTok integration.
        
        CRITICAL: Use subscribe_sync for reliable event handling without asyncio loop.
        
        SOTA 2026 FIX: Only subscribe to brain.visual.request (NOT visual.request).
        BrainRouter already forwards visual.request → brain.visual.request, so subscribing
        to both caused DOUBLE generation (canvas received same prompt twice).
        """
        if self.event_bus:
            if hasattr(self.event_bus, 'subscribe_sync'):
                self.event_bus.subscribe_sync("brain.visual.request", self._on_visual_request)
                logger.info("✅ Visual Canvas connected to EventBus (subscribe_sync, brain.visual.request only)")
            else:
                self.event_bus.subscribe("brain.visual.request", self._on_visual_request)
                logger.info("✅ Visual Canvas connected to EventBus (async, brain.visual.request only)")
        logger.info("🎨 VisualCreationCanvas initialized with SOTA 2026 backends")
    
    def _on_visual_request(self, data: Dict[str, Any]):
        """Handle visual request from EventBus.
        
        COMPLETE AI-POWERED FLOW:
        1. User: "Create X" → Thoth AI tab / Creative Studio
        2. visual.request → BrainRouter → brain.visual.request
        3. THIS METHOD receives brain.visual.request
        4. Routes to single or multi-engine orchestration
        5. Publishes live progress updates
        6. Displays final result in GUI
        
        SOTA 2026 FIX: Includes request deduplication to prevent double generation.
        """
        prompt = data.get("prompt", "")
        request_id = data.get("request_id", f"canvas_{int(time.time() * 1000)}")
        
        # SOTA 2026 FIX: Deduplicate requests to prevent double generation
        if not hasattr(self, '_processed_request_ids'):
            self._processed_request_ids = set()
        if request_id in self._processed_request_ids:
            logger.debug(f"⏭️ Skipping duplicate visual request: {request_id}")
            return
        self._processed_request_ids.add(request_id)
        # Keep set bounded
        if len(self._processed_request_ids) > 50:
            self._processed_request_ids = set(list(self._processed_request_ids)[-25:])
        if prompt:
            mode = data.get("mode", "auto")  # Default to "auto" for intelligent routing
            
            # SOTA 2026 FIX: Publish "processing started" event
            if self.event_bus:
                self.event_bus.publish("visual.generation.started", {
                    "request_id": request_id,
                    "prompt": prompt[:100],
                    "mode": mode,
                    "message": "🧠 Kingdom AI Brain → Visual Canvas - analyzing request..."
                })
                logger.info(f"📡 Visual Canvas received brain.visual.request: {prompt[:80]}...")
            
            # Show immediate visual feedback
            if HAS_PYQT6 and hasattr(self, 'image_label'):
                self._display_stack.setCurrentWidget(self.image_label)
                self.image_label.setText(f"🎨 Generating: {prompt[:80]}...\n\n⏳ Please wait...")
                self.image_label.setStyleSheet("""
                    QLabel {
                        background-color: #1e1e1e;
                        border: 2px solid #17a2b8;
                        border-radius: 8px;
                        color: #17a2b8;
                        font-size: 16px;
                    }
                """)
            
            # Auto-show canvas if hidden
            if not self.isVisible():
                # Keep it embedded; avoid creating a separate top-level window.
                pass
            
            # SOTA 2026 UNIFIED: Use new create() method with multi-engine support
            # This automatically detects complexity and routes to single or multiple engines
            prompt_lower = prompt.lower()
            explicit_all_engines_phrase = any(
                k in prompt_lower
                for k in (
                    "all engines",
                    "all engine libraries",
                    "unified multi engine",
                    "system wide unified",
                    "force orchestrator",
                )
            )
            force_policy_hint = bool(
                data.get("force_orchestrator")
                or data.get("use_all_engine_libraries")
                or data.get("system_wide_unified_context")
                or str(data.get("orchestration_policy", "")).lower().startswith("all_engines")
            )
            # Respect prompt wording first: only force all-engines when explicitly requested.
            force_orchestrator = bool(data.get("force_orchestrator_explicit")) or explicit_all_engines_phrase
            if force_policy_hint and not force_orchestrator:
                logger.info(
                    "🧭 Ignoring legacy all-engines policy flags; routing by prompt semantics"
                )
            if force_orchestrator:
                mode = "multi"
            config = {
                "video_backend": data.get("video_backend"),
                "quality_preset": data.get("quality_preset"),
                "num_frames": data.get("num_frames"),
                "fps": data.get("fps"),
                "force_orchestrator": force_orchestrator,
                "force_orchestrator_explicit": force_orchestrator,
                "use_all_engine_libraries": bool(data.get("use_all_engine_libraries")),
                "system_wide_unified_context": bool(data.get("system_wide_unified_context")),
                "engine_scope": data.get("engine_scope", "auto"),
                "pipeline": data.get("pipeline", "auto"),
                "orchestration_policy": data.get("orchestration_policy", "auto"),
                "knowledge_sources": data.get("knowledge_sources", []),
            }
            
            self.create(prompt, mode=mode, config=config, request_id=request_id)

    def _dispatch_generate_to_worker(self, request_id: str, prompt: str) -> None:
        """Dispatch generation request from canvas to worker thread safely."""
        if not self._worker:
            logger.error("VisualCreationCanvas worker not initialized")
            return
        if not self._worker_thread or not self._worker_thread.isRunning():
            logger.error("VisualCreationCanvas worker thread not running")
            return
        if not hasattr(self._worker, "_generate_signal"):
            logger.error("VisualCreationCanvas worker missing _generate_signal")
            return
        self._worker._generate_signal.emit(request_id, prompt, self._generation_config)
        logger.info(
            "🎨 Generation dispatched to worker thread: %s (mode=%s)",
            request_id,
            self._generation_config.mode,
        )
    
    def generate_from_prompt(self, prompt: str, mode: str = "image"):
        """Generate image or video from prompt.
        
        Args:
            prompt: Text description of what to create
            mode: 'image' for still image, 'video' for animated GIF
        """
        if not HAS_PYQT6:
            logger.error("PyQt6 not available")
            return
        
        if not self._worker:
            logger.error("VisualCreationCanvas worker not initialized")
            return
        
        request_id = f"canvas_{int(time.time() * 1000)}"
        
        # Set mode on config so worker routes correctly
        self._generation_config.mode = mode
        logger.info(f"🎨 generate_from_prompt: mode={mode}, prompt={prompt[:60]}")
        
        # Ensure worker thread is running
        if not self._worker_thread or not self._worker_thread.isRunning():
            logger.warning("Worker thread not running, starting now...")
            if not self._worker_thread:
                self._worker_thread = QThread()
                self._worker.moveToThread(self._worker_thread)
                # Reconnect signals
                if hasattr(self._worker, 'generation_started'):
                    self._worker.generation_started.connect(self._on_generation_started)
                if hasattr(self._worker, 'generation_complete'):
                    self._worker.generation_complete.connect(self._on_generation_complete)
                if hasattr(self._worker, 'generation_progress'):
                    self._worker.generation_progress.connect(self._on_generation_progress)
                if hasattr(self._worker, 'generation_error'):
                    self._worker.generation_error.connect(self._on_generation_error)
            self._worker_thread.start()
            # Give the event loop a moment to bring the worker thread up.
            QTimer.singleShot(120, lambda rid=request_id, p=prompt: self._dispatch_generate_to_worker(rid, p))
            return
        
        # SOTA 2026 FIX: Use signal to invoke on worker thread (PyQt6-compatible)
        self._dispatch_generate_to_worker(request_id, prompt)
    
    # =========================================================================
    # SOTA 2026: VIDEO GENERATION AND DISPLAY
    # =========================================================================
    
    def generate_video_from_prompt(self, prompt: str, request_id: Optional[str] = None):
        """Generate video from prompt using Redis Video Service (kingdom-video environment).
        
        SOTA 2026: Routes to redis_video_service.py which supports:
        - Mochi 1 (best quality, 10B params)
        - CogVideoX (fast, good quality)
        - AnimateLCM (real-time, ~8 steps)
        - LTXVideo (balanced)
        - HunyuanVideo (Chinese scenes)
        """
        if not self._video_redis_client:
            logger.error("❌ Video Redis client not available - cannot generate video")
            if self.event_bus:
                self.event_bus.publish("visual.generation.error", {
                    "request_id": request_id,
                    "error": "Video service not available",
                    "mode": "video"
                })
            return
        
        if not request_id:
            request_id = f"video_{int(time.time() * 1000)}"
        
        try:
            import json
            import threading
            
            logger.info(f"🎬 Publishing video request to Redis Video Service: {prompt[:50]}...")
            
            # Show generating status in GUI
            if HAS_PYQT6 and hasattr(self, 'image_label'):
                self.image_label.setText("🎬 Generating video...\nThis may take a few minutes")
                self.image_label.setStyleSheet("""
                    QLabel {
                        background-color: #1e1e1e;
                        border: 2px solid #9b59b6;
                        border-radius: 8px;
                        color: #9b59b6;
                        font-size: 16px;
                    }
                """)
            
            # Publish request to video service
            request_data = {
                'request_id': request_id,
                'prompt': prompt,
                'num_frames': 49,  # ~2 seconds at 24fps
                'width': 848,
                'height': 480,
                'fps': 24
            }
            
            # Publish to video generation channel
            self._video_redis_client.publish('video.generate', json.dumps(request_data))
            logger.info(f"✅ Video request published to Redis - request_id: {request_id}")
            
            # Start listener thread for video response
            def listen_for_video_response():
                pubsub = self._video_redis_client.pubsub()
                pubsub.subscribe('video.generated', 'video.status')
                
                timeout_start = time.time()
                timeout_seconds = 300  # 5 minutes max for video generation
                
                for message in pubsub.listen():
                    # Check timeout
                    if time.time() - timeout_start > timeout_seconds:
                        logger.warning(f"⏰ Video generation timeout for {request_id}")
                        break
                    
                    if message['type'] == 'message':
                        try:
                            data = json.loads(message['data'])
                            msg_request_id = data.get('request_id')
                            
                            if msg_request_id != request_id:
                                continue  # Not our request
                            
                            channel = message['channel']
                            
                            if channel == 'video.status':
                                status = data.get('status', '')
                                progress = data.get('progress', 0)
                                logger.info(f"🎬 Video progress: {status} ({progress}%)")
                                
                                # Update GUI with progress
                                if HAS_PYQT6 and hasattr(self, 'image_label'):
                                    try:
                                        from PyQt6.QtCore import QMetaObject, Qt
                                        # Thread-safe GUI update
                                        self.image_label.setText(f"🎬 {status}\n{progress}%")
                                    except:
                                        pass
                            
                            elif channel == 'video.generated':
                                status = data.get('status')
                                if status == 'complete':
                                    video_path = data.get('video_path')
                                    logger.info(f"✅ Video generated: {video_path}")
                                    
                                    # Display video thumbnail in GUI
                                    self._display_video_result(video_path, request_id, prompt)
                                    
                                    # Publish completion event
                                    if self.event_bus:
                                        self.event_bus.publish("visual.generated", {
                                            "video_path": video_path,
                                            "request_id": request_id,
                                            "prompt": prompt,
                                            "mode": "video",
                                            "backend": data.get('backend', 'redis_video_service')
                                        })
                                    
                                    pubsub.unsubscribe()
                                    break
                                    
                                elif status == 'error':
                                    error = data.get('error', 'Unknown error')
                                    logger.error(f"❌ Video generation error: {error}")
                                    if HAS_PYQT6 and hasattr(self, 'image_label'):
                                        self.image_label.setText(f"❌ Video failed: {error}")
                                    pubsub.unsubscribe()
                                    break
                                    
                        except json.JSONDecodeError as e:
                            logger.debug(f"Non-JSON message: {e}")
                        except Exception as e:
                            logger.error(f"Error processing video response: {e}")
            
            # Start listener in background thread
            listener_thread = threading.Thread(
                target=listen_for_video_response,
                daemon=True,
                name=f"VideoResponseListener_{request_id}"
            )
            listener_thread.start()
            
        except Exception as e:
            logger.error(f"❌ Failed to request video generation: {e}")
            if self.event_bus:
                self.event_bus.publish("visual.generation.error", {
                    "request_id": request_id,
                    "error": str(e),
                    "mode": "video"
                })
    
    def _display_video_result(self, video_path: str, request_id: str, prompt: str):
        """Display video result with SOTA 2026 continuous playback.
        
        SOTA 2026: Uses RealTimeVideoPlayer for continuous playback with:
        - QMediaPlayer + QVideoSink architecture
        - Hardware-accelerated decoding
        - AI frame processing integration
        - Memory-efficient frame buffer (max 3 frames)
        
        Falls back to static thumbnail if video player unavailable.
        """
        if not HAS_PYQT6:
            return
        
        if not video_path or not Path(video_path).exists():
            logger.error(f"Video file not found: {video_path}")
            return
        
        # Store video path
        self._last_generated_video = video_path
        
        # SOTA 2026: Use RealTimeVideoPlayer for continuous playback
        if self._video_player is not None:
            try:
                # Load video into player
                if self._video_player.load_video(video_path):
                    # Switch to video player view
                    self._display_stack.setCurrentWidget(self._video_player)
                    
                    # Auto-start playback with loop enabled
                    self._video_player.set_loop(True)
                    self._video_player.play()
                    
                    logger.info(f"✅ SOTA 2026: Video playback started: {video_path}")
                    
                    # Publish playback started event
                    if self.event_bus:
                        self.event_bus.publish("video.playback.started", {
                            "video_path": video_path,
                            "request_id": request_id,
                            "prompt": prompt
                        })
                    
                    return
                else:
                    logger.warning(f"⚠️ Video player failed to load, using thumbnail fallback")
            except Exception as e:
                logger.error(f"Video player error: {e}, using thumbnail fallback")
        
        # Fallback: Display static thumbnail (original behavior)
        self._display_video_thumbnail(video_path, request_id, prompt)
    
    def _display_video_thumbnail(self, video_path: str, request_id: str, prompt: str):
        """Display static video thumbnail (fallback when video player unavailable)."""
        try:
            import cv2
            
            # Switch to image label view
            self._display_stack.setCurrentWidget(self.image_label)
            
            # Extract first frame as thumbnail
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            cap.release()
            
            if ret and frame is not None:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                
                # Create QImage from frame
                qimage = QImage(frame_rgb.tobytes(), w, h, bytes_per_line, QImage.Format.Format_RGB888)
                
                if not qimage.isNull():
                    pixmap = QPixmap.fromImage(qimage)
                    
                    # Scale to fit label
                    scaled = pixmap.scaled(
                        self.image_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    
                    self.image_label.setPixmap(scaled)
                    self.image_label.setStyleSheet("""
                        QLabel {
                            background-color: #1e1e1e;
                            border: 2px solid #9b59b6;
                            border-radius: 8px;
                        }
                    """)
                    
                    logger.info(f"✅ Video thumbnail displayed: {video_path}")
                    
                    return
            
            # Couldn't extract frame - show text instead
            self.image_label.setText(f"🎬 Video ready!\n{Path(video_path).name}\nClick to play")
            logger.warning(f"Could not extract thumbnail from video: {video_path}")
                
        except ImportError:
            # OpenCV not available - show text
            self.image_label.setText(f"🎬 Video generated!\n{Path(video_path).name}")
            logger.info(f"Video generated (cv2 not available for thumbnail): {video_path}")
        except Exception as e:
            logger.error(f"Error displaying video thumbnail: {e}")
            self.image_label.setText(f"🎬 Video ready: {Path(video_path).name}")
    
    def _on_video_playback_finished(self):
        """Handle video playback finished signal."""
        logger.info("🎬 Video playback finished")
        if self.event_bus:
            self.event_bus.publish("video.playback.finished", {
                "video_path": self._last_generated_video
            })
    
    def _on_video_error(self, error_msg: str):
        """Handle video player error."""
        logger.error(f"🎬 Video player error: {error_msg}")
        # Fallback to thumbnail display
        if self._last_generated_video:
            self._display_video_thumbnail(self._last_generated_video, "", "")
    
    def stop_video_playback(self):
        """Stop current video playback and show image label."""
        if self._video_player:
            self._video_player.stop()
        self._display_stack.setCurrentWidget(self.image_label)
    
    def play_last_video(self):
        """Replay the last generated video."""
        if self._last_generated_video and self._video_player:
            self._display_video_result(self._last_generated_video, "", "")
    
    def _on_generation_started(self, request_id: str):
        """Handle generation started."""
        logger.info(f"🎨 Generation started: {request_id}")
    
    def _on_generation_complete(self, image, metadata):
        """Handle generation complete - DISPLAY IMAGE, VIDEO, or ANIMATED GIF."""
        if not HAS_PYQT6:
            return
        
        image_path = metadata.get("image_path")
        video_path = metadata.get("video_path") or ""
        is_video = metadata.get("type") == "video"
        is_gif = image_path and str(image_path).lower().endswith(".gif")
        is_mp4 = (video_path and str(video_path).lower().endswith(".mp4")) or \
                 (image_path and str(image_path).lower().endswith(".mp4"))
        
        # MP4 video: route through the real video player (not QMovie)
        if (is_video or is_mp4) and not is_gif:
            mp4_path = video_path or image_path
            if mp4_path and Path(mp4_path).exists():
                request_id = metadata.get("request_id", "")
                prompt = metadata.get("prompt", "")
                self._display_video_result(str(mp4_path), request_id, prompt)
                self._last_displayed_image = str(mp4_path)
                if self.image_generated:
                    self.image_generated.emit(image, metadata)
                return
        
        if image_path and Path(image_path).exists():
            # Stop any video playback and switch to image view
            if self._video_player:
                self._video_player.stop()
            self._display_stack.setCurrentWidget(self.image_label)
            
            if is_gif:
                # ANIMATED GIF playback with QMovie
                from PyQt6.QtGui import QMovie
                movie = QMovie(image_path)
                if movie.isValid():
                    label_size = self.image_label.size()
                    movie.setScaledSize(label_size)
                    self.image_label.setMovie(movie)
                    movie.start()
                    self._current_movie = movie
                    self._last_generated_video = image_path
                    logger.info(f"🎬 Playing animated GIF: {image_path}")
                else:
                    logger.warning(f"QMovie invalid for: {image_path}")
                    self.image_label.setText(f"🎬 Video saved but can't play: {Path(image_path).name}")
                
                self.image_label.setStyleSheet("""
                    QLabel {
                        background-color: #1e1e1e;
                        border: 2px solid #9b59b6;
                        border-radius: 8px;
                    }
                """)
            else:
                # Static image display
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        self.image_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.image_label.setPixmap(scaled)
                    self.image_label.setStyleSheet("""
                        QLabel {
                            background-color: #1e1e1e;
                            border: 2px solid #28a745;
                            border-radius: 8px;
                        }
                    """)
            
            self._last_displayed_image = image_path
        
        if self.image_generated:
            self.image_generated.emit(image, metadata)
    
    def upload_and_restore_video(self, video_path: str, config: Optional[Dict[str, Any]] = None):
        """Upload video and trigger AI restoration pipeline.
        
        Args:
            video_path: Path to input video file
            config: Optional restoration config:
                - colorize_method: 'ddcolor', 'deoldify', or 'enhancement'
                - colorize_strength: 0.0-1.0
                - enable_colorize: True/False
                - upscale_factor: 2 or 4
                - enable_upscale: True/False
                - enable_face_enhance: True/False
                - enable_detect: True/False (player detection)
                - target_width: 3840 (4K)
                - target_height: 2160 (4K)
        """
        if not HAS_VIDEO_RESTORER:
            logger.error("❌ AI Video Restorer not available")
            if HAS_PYQT6:
                self.image_label.setText("❌ AI Video Restorer not installed\n\nInstall with:\npip install gfpgan realesrgan ultralytics supervision")
            return
        
        # Validate video file exists
        video_file = Path(video_path)
        if not video_file.exists():
            logger.error(f"❌ Video file not found: {video_path}")
            if HAS_PYQT6:
                self.image_label.setText(f"❌ Video not found:\n{video_path}")
            return
        
        logger.info(f"🎬 Uploading video for restoration: {video_file.name}")
        
        # Update UI to show processing
        if HAS_PYQT6:
            self.image_label.setText(f"🎬 AI Video Restoration\n\nProcessing: {video_file.name}\n\nStages:\n• Colorization (DDColor/DeOldify)\n• 4K Upscaling (RealESRGAN)\n• Face Enhancement (GFPGAN)\n• Player Detection (YOLO)\n\nThis may take several minutes...")
            self.image_label.setStyleSheet("""
                QLabel {
                    background-color: #1e1e1e;
                    border: 2px solid #ff6b6b;
                    border-radius: 8px;
                    color: #ff6b6b;
                    padding: 20px;
                }
            """)
        
        # Generate request ID
        request_id = f"restore_{int(time.time() * 1000)}"
        
        # Trigger restoration on worker thread
        if self._worker and self._worker_thread:
            # Ensure worker thread is running
            if not self._worker_thread.isRunning():
                self._worker_thread.start()
            
            # Call restore_video on worker thread
            from PyQt6.QtCore import QMetaObject, Q_ARG
            QMetaObject.invokeMethod(
                self._worker,
                "restore_video",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, request_id),
                Q_ARG(str, str(video_path)),
                Q_ARG(object, config)
            )
            
            logger.info(f"✅ Video restoration queued: {request_id}")
        else:
            logger.error("❌ Worker thread not available")
            if HAS_PYQT6:
                self.image_label.setText("❌ Worker thread not initialized")
    
    def _on_generation_progress(self, request_id, progress, preview_image):
        """Handle generation progress - DISPLAY LIVE PREVIEW."""
        if not HAS_PYQT6:
            return
        
        # Switch to image label view for preview
        self._display_stack.setCurrentWidget(self.image_label)
        
        # Display preview image if available
        if preview_image and not preview_image.isNull():
            pixmap = QPixmap.fromImage(preview_image)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.image_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled)
                self.image_label.setStyleSheet("""
                    QLabel {
                        background-color: #1e1e1e;
                        border: 2px solid #17a2b8;
                        border-radius: 8px;
                    }
                """)
                
    
    def _on_generation_error(self, request_id, error):
        """Handle generation error."""
        logger.error(f"Generation error ({request_id}): {error}")
        if HAS_PYQT6:
            # Switch to image label view for error display
            self._display_stack.setCurrentWidget(self.image_label)
            self.image_label.setText(f"❌ Generation failed: {error}")
            self.image_label.setStyleSheet("""
                QLabel {
                    background-color: #1e1e1e;
                    border: 2px solid #dc3545;
                    border-radius: 8px;
                    color: #dc3545;
                }
            """)
    
    # =========================================================================
    # SOTA 2026: VIDEO EDITING CONTROL PANEL IMPLEMENTATION
    # =========================================================================
    
    def _on_timeline_scrub(self, value: int):
        """Handle timeline scrubber movement."""
        if not self._current_video_path:
            return
        time_seconds = value / 1000.0
        self._playback_position = time_seconds
        hours = int(time_seconds // 3600)
        minutes = int((time_seconds % 3600) // 60)
        seconds = int(time_seconds % 60)
        frames = int((time_seconds % 1) * 30)
        self._timecode_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}")
        if self.event_bus:
            self.event_bus.publish("video.scrub", {"position": time_seconds})
    
    def _toggle_playback(self):
        """Toggle play/pause."""
        self._is_playing = not self._is_playing
        self._play_btn.setText("⏸ Pause" if self._is_playing else "▶ Play")
        logger.info(f"{'▶️ Playing' if self._is_playing else '⏸ Paused'}")
        if self.event_bus:
            self.event_bus.publish("video.playback", {"playing": self._is_playing})
    
    def _stop_playback(self):
        """Stop playback."""
        self._is_playing = False
        self._play_btn.setText("▶ Play")
        self._playback_position = 0.0
        self._timeline_scrubber.setValue(0)
        logger.info("⏹ Stopped")
    
    def _prev_frame(self):
        """Go to previous frame."""
        self._playback_position = max(0, self._playback_position - 1/30.0)
        self._timeline_scrubber.setValue(int(self._playback_position * 1000))
    
    def _next_frame(self):
        """Go to next frame."""
        self._playback_position += 1/30.0
        self._timeline_scrubber.setValue(int(self._playback_position * 1000))
    
    def _cut_at_playhead(self):
        """Cut video at current playhead position."""
        cut_time = self._playback_position
        self._cut_markers.append(cut_time)
        self._markers_label.setText(f"Cuts: {len(self._cut_markers)} ({', '.join([f'{t:.2f}s' for t in self._cut_markers[:3]])}{'...' if len(self._cut_markers) > 3 else ''})")
        logger.info(f"✂️ Cut added at {cut_time:.2f}s")
        if self.event_bus:
            self.event_bus.publish("video.cut", {"time": cut_time, "total_cuts": len(self._cut_markers)})
    
    def _trim_selection(self):
        """Trim selected region."""
        logger.info("✂️ Trim operation")
        if self.event_bus:
            self.event_bus.publish("video.trim", {"position": self._playback_position})
    
    def _split_at_playhead(self):
        """Split clip at playhead."""
        logger.info(f"⚡ Split at {self._playback_position:.2f}s")
        if self.event_bus:
            self.event_bus.publish("video.split", {"time": self._playback_position})
    
    def _save_project(self):
        """Save project file."""
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "Kingdom AI Project (*.kaip);;JSON (*.json)")
        if file_path:
            project_data = {'video_path': self._current_video_path, 'cuts': self._cut_markers, 'playback_position': self._playback_position}
            import json
            with open(file_path, 'w') as f:
                json.dump(project_data, f, indent=2)
            logger.info(f"💾 Project saved: {file_path}")
            if self.event_bus:
                self.event_bus.publish("video.project.saved", {"path": file_path})
    
    def _export_video(self):
        """Export final video."""
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Video", "", "MP4 (*.mp4);;MOV (*.mov)")
        if file_path:
            logger.info(f"🎬 Exporting to: {file_path}")
            if self.event_bus:
                self.event_bus.publish("video.export", {"output_path": file_path, "cuts": self._cut_markers, "source": self._current_video_path})
    
    def _undo(self):
        """Undo last action."""
        if self._cut_markers:
            removed = self._cut_markers.pop()
            logger.info(f"↶ Undo: Removed cut at {removed:.2f}s")
            self._markers_label.setText(f"Cuts: {len(self._cut_markers)}")
    
    def create(self, prompt: str, mode: str = "auto", config: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None):
        """
        UNIFIED CREATION METHOD - Intelligently routes to single or multiple engines.
        
        This is the MAIN ENTRY POINT for all creation requests.
        Analyzes the prompt and decides whether to use:
        - Single engine (simple image/video)
        - Multiple engines (complex multi-step creations)
        
        Args:
            prompt: Natural language creation request
            mode: "auto" (intelligent routing), "image", "video", "multi"
            config: Optional configuration overrides
        
        Examples:
            create("A fantasy castle")  # → Single engine (image)
            create("Create a holographic medical heart animation")  # → Multi-engine
            create("Generate a fantasy world map with animated clouds")  # → Multi-engine
        """
        if not HAS_PYQT6:
            return
        
        logger.info(f"🎨 Creation request: {prompt[:100]}...")
        
        config = config or {}

        explicit_all_engines_phrase = any(
            k in prompt.lower()
            for k in (
                "all engines",
                "all engine libraries",
                "unified multi engine",
                "system wide unified",
                "force orchestrator",
            )
        )

        force_policy_hint = bool(
            config.get("force_orchestrator")
            or config.get("use_all_engine_libraries")
            or config.get("system_wide_unified_context")
            or str(config.get("orchestration_policy", "")).lower().startswith("all_engines")
            or str(config.get("pipeline", "")).lower() in ("unified_multi_engine", "all_engines")
            or str(config.get("engine_scope", "")).lower() == "all"
        )
        # Only explicit wording (or explicit flag) should force heavy orchestration.
        force_orchestrator = bool(config.get("force_orchestrator_explicit")) or explicit_all_engines_phrase
        if force_policy_hint and not force_orchestrator:
            logger.info("🧭 Legacy all-engines config detected; using wording-based routing instead")

        # SOTA 2026: Use orchestrator as DEFAULT for mode=auto (collective - all engines contribute)
        is_complex = self._is_complex_request(prompt) if mode == "auto" else (mode == "multi")
        prompt_lower = prompt.lower()
        engineering_unified = (
            ("exploded" in prompt_lower or "assembly" in prompt_lower or "disassembled" in prompt_lower)
            and any(k in prompt_lower for k in ("car", "supercar", "engine", "mechanical", "cad", "engineering", "component"))
        )
        # Collective by default: orchestrator routes to appropriate engine(s) for every request
        use_orchestrator_default = (mode == "auto" and self._use_orchestrator)
        
        # SOTA 2026: Detect fabrication requests (3D printing, PCB, laser, materials)
        fabrication_mode = self._detect_fabrication_mode(prompt)
        
        if fabrication_mode:
            # Route to fabrication engine via Redis
            logger.info(f"🏭 Fabrication request detected: mode={fabrication_mode}")
            self._create_fabrication(prompt, fabrication_mode, config)
        elif engineering_unified and self._use_orchestrator:
            # Keep direct video path for engineering exploded requests unless the
            # caller explicitly forces all-engines orchestration. This preserves
            # the working CAD+trimesh motion pipeline in ImageGenerationWorker.
            if force_orchestrator:
                logger.info("🛠️ Engineering exploded request -> forcing unified multi-engine orchestrator")
                self._create_with_orchestrator(prompt, config)
                return
            logger.info("🛠️ Engineering exploded request -> using direct engineering video pipeline")
            request_id = request_id or f"req_{int(time.time() * 1000)}"
            if self._worker:
                self._generation_config.mode = "video"
                if self._worker_thread and not self._worker_thread.isRunning():
                    self._worker_thread.start()
                self._worker._generate_signal.emit(request_id, prompt, self._generation_config)
            return
        elif force_orchestrator and self._use_orchestrator:
            logger.info("🧠 Explicit all-engines request detected -> forcing multi-engine orchestrator")
            self._create_with_orchestrator(prompt, config)
        elif (is_complex or use_orchestrator_default) and self._use_orchestrator:
            # Use multi-engine orchestration (DEFAULT for Creation Studio - collective)
            logger.info("🎬 Creation Studio: routing through unified orchestrator (all engines contribute)")
            self._create_with_orchestrator(prompt, config)
        else:
            # Use single engine (image or video)
            request_id = request_id or f"req_{int(time.time() * 1000)}"
            
            is_video_request = (
                mode in ("video", "animation")
                or 'video' in prompt.lower()
                or 'animation' in prompt.lower()
                or 'animated' in prompt.lower()
                or 'moving' in prompt.lower()
                or 'motion' in prompt.lower()
            )
            if is_video_request:
                logger.info("🎬 Single engine: Video generation")
                if self._worker:
                    # CRITICAL: ensure worker routes to video pipeline.
                    self._generation_config.mode = "video"
                    # Ensure worker thread is running
                    if self._worker_thread and not self._worker_thread.isRunning():
                        self._worker_thread.start()
                    self._worker._generate_signal.emit(request_id, prompt, self._generation_config)
            else:
                logger.info("🎨 Single engine: Image generation")
                if self._worker:
                    self._generation_config.mode = "image"
                    # Ensure worker thread is running
                    if self._worker_thread and not self._worker_thread.isRunning():
                        self._worker_thread.start()
                    self._worker._generate_signal.emit(request_id, prompt, self._generation_config)
    
    def _detect_fabrication_mode(self, prompt: str) -> Optional[str]:
        """
        Detect if prompt is a fabrication/simulation request.
        
        Returns mode string or None if not a routed request.
        SOTA 2026: Routes to creation_engine_service.py handlers.
        """
        p = prompt.lower()
        
        # Blueprint / Technical Drawing / DXF (mechanical CAD documentation)
        # Check BEFORE pcb so "assembly schematic" routes to blueprint, not circuit
        blueprint_keywords = [
            "blueprint", "technical drawing", "dxf", "dimensioned drawing",
            "orthographic", "floor plan", "assembly diagram", "block diagram",
            "assembly schematic", "mechanical schematic", "system schematic",
            "exploded view diagram", "parts list", "bom drawing",
        ]
        if any(kw in p for kw in blueprint_keywords):
            return "blueprint"
        
        # PCB / Circuit / Electronics (schematic = circuit schematic)
        pcb_keywords = [
            "pcb", "circuit board", "schematic", "circuit design", "gerber",
            "electronics", "pcb layout", "trace", "solder", "kicad",
            "jlcpcb", "pcbway", "voltera", "conductive ink", "copper trace",
        ]
        if any(kw in p for kw in pcb_keywords):
            return "pcb"
        
        # 3D Printing
        print_keywords = [
            "3d print", "print a", "stl", "gcode", "g-code", "filament",
            "fdm", "sla", "sls", "slicer", "orcaslicer", "prusaslicer",
            "cura", "octoprint", "klipper", "nozzle", "infill", "layer height",
        ]
        if any(kw in p for kw in print_keywords):
            return "3d_print"
        
        # CAD / Mechanical Design
        cad_keywords = [
            "cad", "mechanical design", "parametric", "cadquery", "solidpython",
            "openscad", "freecad", "step file", "technical drawing",
            "engineering drawing", "dimension", "tolerance",
        ]
        if any(kw in p for kw in cad_keywords):
            return "cad"
        
        # Laser Engraving / Cutting
        laser_keywords = [
            "laser engrav", "laser cut", "laser mark", "engrave",
            "lightburn", "lasergrbl", "rayforge", "grbl", "laser etch",
        ]
        if any(kw in p for kw in laser_keywords):
            return "laser"
        
        # Materials Recommendation
        materials_keywords = [
            "recommend material", "material for", "what filament",
            "best material", "peek", "carbon fiber filament", "metal filament",
            "ultrafuse", "conductive pla", "tpu", "flexible filament",
            "nylon filament", "polycarbonate filament",
        ]
        if any(kw in p for kw in materials_keywords):
            return "materials"

        # Physics simulation: CFD / wind tunnel / turbulence
        cfd_keywords = [
            "cfd", "wind tunnel", "aerodynamic", "aerodynamics", "turbulence",
            "airflow", "tailwind", "drag coefficient", "lift coefficient",
            "openfoam", "su2", "pyfr",
        ]
        if any(kw in p for kw in cfd_keywords):
            return "cfd"

        # Structural simulation: stress/strain/deformation
        structural_keywords = [
            "structural analysis", "stress analysis", "strain", "fatigue",
            "deformation", "fea", "fem", "load case", "buckling", "modal analysis",
            "vibration", "fenics", "sfepy",
        ]
        if any(kw in p for kw in structural_keywords):
            return "structural"

        # Water/buoyancy/free-surface simulation
        buoyancy_keywords = [
            "buoyancy", "water surface", "floating", "ship hull", "boat stability",
            "hydrodynamic", "wave simulation", "sloshing", "free surface", "sph",
            "interfoam", "pysph",
        ]
        if any(kw in p for kw in buoyancy_keywords):
            return "buoyancy"

        # Chemistry / thermal / metallurgy simulation
        chemistry_keywords = [
            "chemistry", "chemical reaction", "reactor", "combustion", "cantera",
            "thermodynamic", "thermal", "heat transfer", "heat sensitive",
            "metallurgy", "alloy", "phase diagram", "materials chemistry",
        ]
        if any(kw in p for kw in chemistry_keywords):
            return "chemistry"

        # Webcam/image-based reverse engineering
        webcam_keywords = [
            "webcam", "camera rebuild", "reverse engineer from image",
            "image to cad", "image to 3d", "photo to 3d", "reconstruct from image",
            "colmap", "photogrammetry",
        ]
        if any(kw in p for kw in webcam_keywords):
            return "webcam_rebuild"
        
        return None
    
    def _create_fabrication(self, prompt: str, fab_mode: str, config: Optional[Dict[str, Any]] = None):
        """
        Route fabrication request to creation_engine_service.py via Redis.
        
        The service generates data (circuit, STL, G-code, CFD fields, etc.) and
        renders a visual preview PNG that displays in the same QLabel pipeline.
        
        SOTA 2026 Modes:
        pcb, 3d_print, cad, laser, materials, cfd, structural, buoyancy,
        chemistry, webcam_rebuild
        """
        request_id = f"fab_{int(time.time() * 1000)}"
        
        # Show generating status
        if HAS_PYQT6 and hasattr(self, 'image_label'):
            self._display_stack.setCurrentWidget(self.image_label)
            mode_labels = {
                "pcb": "⚡ Designing PCB Circuit",
                "blueprint": "📐 Generating Blueprint / Technical Drawing",
                "3d_print": "🖨 Generating 3D Print",
                "cad": "🔧 Creating CAD Model",
                "laser": "⚡ Generating Laser Engraving",
                "materials": "🧪 Analyzing Materials",
                "cfd": "🌬 Running CFD / Wind Tunnel",
                "structural": "🏗 Running Structural FEA",
                "buoyancy": "🌊 Running Buoyancy Simulation",
                "chemistry": "🔥 Running Thermal/Chemistry Simulation",
                "webcam_rebuild": "📷 Rebuilding from Webcam/Image",
            }
            label = mode_labels.get(fab_mode, "🏭 Processing Fabrication")
            self.image_label.setText(f"{label}\n\n{prompt[:100]}...\n\n⏳ Please wait...")
            self.image_label.setStyleSheet("""
                QLabel {
                    background-color: #1e1e1e;
                    border: 2px solid #ff8c00;
                    border-radius: 8px;
                    color: #ff8c00;
                    font-size: 16px;
                }
            """)
        
        # Publish to Redis with fabrication mode (Redis Quantum Nexus)
        try:
            import json as _json
            import redis as _redis
            
            redis_client = getattr(self, '_redis_client', None)
            if not redis_client:
                try:
                    from core.redis_channels import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
                except ImportError:
                    REDIS_HOST, REDIS_PORT, REDIS_PASSWORD = 'localhost', 6380, 'QuantumNexus2025'
                
                redis_client = _redis.Redis(
                    host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
                    decode_responses=True, socket_timeout=5
                )
                redis_client.ping()
            
            # SOTA 2026: Verify Creation Engine Service is running before publishing
            service_status = redis_client.get('creation.service.status')
            if service_status != 'running':
                err_msg = "Creation Engine Service not running. Start creation_engine_service.py (creation_env) first."
                logger.warning(f"🏭 {err_msg}")
                if hasattr(self, 'generation_error') and self.generation_error:
                    self.generation_error.emit(request_id, err_msg)
                if HAS_PYQT6 and hasattr(self, 'image_label'):
                    self.image_label.setText(f"❌ {err_msg}\n\nRun: python creation_engine_service.py")
                return
            
            request_data = {
                'request_id': request_id,
                'prompt': prompt,
                'mode': fab_mode,
                'config': config or {},
            }
            
            try:
                from core.redis_channels import ImageChannels
                request_channel = ImageChannels.REQUEST
                response_channel = ImageChannels.RESPONSE
                progress_channel = ImageChannels.PROGRESS
            except ImportError:
                request_channel = 'creation.request'
                response_channel = 'creation.response'
                progress_channel = 'creation.progress'
            
            redis_client.publish(request_channel, _json.dumps(request_data))
            logger.info(f"🏭 Fabrication request published: mode={fab_mode}, id={request_id}")
            
            # Listen for response (reuse existing listener pattern)
            from threading import Thread
            
            def listen_fab():
                pubsub = redis_client.pubsub()
                pubsub.subscribe(response_channel, progress_channel)
                for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            data = _json.loads(message['data'])
                            if data.get('request_id') != request_id:
                                continue
                            
                            channel = message['channel']
                            if channel == progress_channel:
                                progress = data.get('progress', 0)
                                status = data.get('status', '')
                                logger.info(f"🏭 Fabrication progress: {progress}% - {status}")
                                if hasattr(self, 'generation_progress') and self.generation_progress:
                                    self.generation_progress.emit(request_id, progress, None)
                                if self.event_bus:
                                    self.event_bus.publish("creation.progress", data)
                            
                            elif channel == response_channel:
                                status = data.get('status')
                                if status == 'complete':
                                    image_path = data.get('image_path')
                                    logger.info(f"✅ Fabrication complete: {image_path}")
                                    
                                    from PIL import Image as _PIL
                                    pil_image = _PIL.open(image_path)
                                    qimage = self._pil_to_qimage(pil_image)
                                    
                                    metadata = {
                                        "backend": f"fabrication_{fab_mode}",
                                        "image_path": image_path,
                                        "width": data.get('width', 1024),
                                        "height": data.get('height', 1024),
                                        "prompt": prompt,
                                        "request_id": request_id,
                                        "type": "image",
                                    }
                                    
                                    if hasattr(self, 'generation_complete') and self.generation_complete:
                                        self.generation_complete.emit(qimage, metadata)
                                    if self.event_bus:
                                        self.event_bus.publish("creation.response", data)
                                    pubsub.close()
                                    break
                                
                                elif status == 'error':
                                    error = data.get('error', 'Unknown')
                                    logger.error(f"❌ Fabrication error: {error}")
                                    if hasattr(self, 'generation_error') and self.generation_error:
                                        self.generation_error.emit(request_id, error)
                                    if self.event_bus:
                                        self.event_bus.publish("creation.response", data)
                                    pubsub.close()
                                    break
                        except Exception as e:
                            logger.error(f"Fabrication listener error: {e}")
            
            Thread(target=listen_fab, daemon=True).start()
            
            # Timeout
            def fab_timeout():
                import time as _time
                _time.sleep(120)
                logger.warning(f"⏱️ Fabrication timeout (120s) for {request_id}")
            Thread(target=fab_timeout, daemon=True).start()
            
        except Exception as e:
            logger.error(f"❌ Fabrication request failed: {e}", exc_info=True)
            if HAS_PYQT6 and hasattr(self, 'image_label'):
                self.image_label.setText(f"❌ Fabrication request failed:\n{e}")
    
    def _is_complex_request(self, prompt: str) -> bool:
        """Analyze if request requires multiple engines."""
        prompt_lower = prompt.lower()
        
        # Check for multi-engine keywords
        multi_engine_keywords = [
            ('medical', 'animation'),
            ('map', 'animated'),
            ('schematic', 'animated'),
            ('holographic', 'animation'),
            ('3d', 'animation'),
            ('reconstruct', 'animation'),
            ('terrain', 'animated'),
        ]
        
        for keyword1, keyword2 in multi_engine_keywords:
            if keyword1 in prompt_lower and keyword2 in prompt_lower:
                return True
        
        # Check for explicit multi-step requests
        multi_step_indicators = [
            'then', 'and then', 'followed by', 'after that',
            'combine', 'merge', 'composite', 'overlay',
            'with animated', 'with motion', 'with particles'
        ]
        
        for indicator in multi_step_indicators:
            if indicator in prompt_lower:
                return True

        # Engineering exploded assembly requests should always use unified orchestration.
        if any(k in prompt_lower for k in ('exploded', 'disassembled', 'assembly sequence', 'parts assembling')):
            if any(k in prompt_lower for k in ('car', 'supercar', 'engine', 'mechanical', 'cad', 'engineering', 'component')):
                return True
        
        return False
    
    def _create_with_orchestrator(self, prompt: str, config: Optional[Dict[str, Any]] = None):
        """Execute multi-engine creation using orchestrator."""
        request_id = f"orchestrator_{int(time.time() * 1000)}"

        # Lazy-load orchestrator with self-healing retries.
        if self._orchestrator is None:
            load_error = None
            for attempt in range(1, 4):
                try:
                    from core.creation_orchestrator import get_orchestrator
                    self._orchestrator = get_orchestrator(event_bus=self.event_bus)
                    # Pre-warm engine registry so first request does not fail due
                    # to lazy-load race/missing imports.
                    if hasattr(self._orchestrator, "_lazy_load_engines"):
                        self._orchestrator._lazy_load_engines()
                    logger.info("✅ Creation orchestrator loaded (attempt %d)", attempt)
                    load_error = None
                    break
                except Exception as e:
                    load_error = e
                    logger.warning("⚠️ Orchestrator load attempt %d failed: %s", attempt, e)
                    time.sleep(0.25 * attempt)
            if self._orchestrator is None:
                err_msg = f"Unified orchestrator unavailable after retries: {load_error}"
                logger.error("❌ %s", err_msg)
                if HAS_PYQT6 and hasattr(self, "image_label"):
                    self.image_label.setText(f"❌ Unified pipeline unavailable\n{err_msg}")
                if self.event_bus:
                    self.event_bus.publish("visual.generation.error", {
                        "request_id": request_id,
                        "prompt": prompt,
                        "error": err_msg,
                        "mode": "multi",
                        "pipeline": "unified",
                    })
                return
        
        # Parse request into multi-engine pipeline
        try:
            pipeline = self._orchestrator.parse_request(prompt)
            if isinstance(config, dict):
                pipeline.metadata.update({
                    "force_orchestrator": bool(config.get("force_orchestrator")),
                    "use_all_engine_libraries": bool(config.get("use_all_engine_libraries")),
                    "system_wide_unified_context": bool(config.get("system_wide_unified_context")),
                    "engine_scope": config.get("engine_scope", "auto"),
                    "pipeline": config.get("pipeline", "auto"),
                    "orchestration_policy": config.get("orchestration_policy", "auto"),
                    "knowledge_sources": config.get("knowledge_sources", []),
                })
            logger.info(f"🎬 Pipeline created: {pipeline.description}")
            logger.info(f"   Engines: {[task.engine.value for task in pipeline.tasks]}")
            
            # Update UI to show pipeline execution
            if HAS_PYQT6:
                self.image_label.setText(f"🎬 Multi-Engine Creation\n{pipeline.description}\n\nEngines: {len(pipeline.tasks)}")
                self.image_label.setStyleSheet("""
                    QLabel {
                        background-color: #1e1e1e;
                        border: 2px solid #17a2b8;
                        border-radius: 8px;
                        color: #17a2b8;
                    }
                """)
            
            # Execute pipeline asynchronously with retry before surfacing error.
            import asyncio
            import threading
            
            def run_pipeline():
                last_error = None
                working_pipeline = pipeline
                try:
                    for attempt in range(1, 3):
                        # Create event loop for this thread
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            result = loop.run_until_complete(self._orchestrator.execute_pipeline(working_pipeline))
                            if result.success:
                                logger.info("✅ Pipeline complete: %.2fs (attempt %d)", result.execution_time, attempt)
                                self._display_pipeline_result(result)
                                return
                            last_error = result.error or "Unknown pipeline error"
                            logger.warning("⚠️ Pipeline attempt %d returned failure: %s", attempt, last_error)
                        finally:
                            loop.close()
                        # Self-heal retry: rebuild pipeline once and try again.
                        if attempt == 1:
                            try:
                                pipeline_retry = self._orchestrator.parse_request(prompt)
                                pipeline_retry.metadata.update(getattr(working_pipeline, "metadata", {}))
                                working_pipeline = pipeline_retry
                            except Exception as retry_parse_error:
                                last_error = f"Retry parse failed: {retry_parse_error}"
                                break
                    err_msg = f"Multi-engine pipeline failed after retries: {last_error or 'unknown error'}"
                    logger.error("❌ %s", err_msg)
                    if HAS_PYQT6 and hasattr(self, "image_label"):
                        self.image_label.setText(f"❌ Multi-Engine Creation Failed\n{err_msg}")
                    if self.event_bus:
                        self.event_bus.publish("visual.generation.error", {
                            "request_id": request_id,
                            "prompt": prompt,
                            "error": err_msg,
                            "mode": "multi",
                            "pipeline": "unified",
                        })
                except Exception as e:
                    logger.error(f"Pipeline execution error: {e}", exc_info=True)
                    if HAS_PYQT6 and hasattr(self, "image_label"):
                        self.image_label.setText(f"❌ Multi-Engine Creation Error\n{e}")
                    if self.event_bus:
                        self.event_bus.publish("visual.generation.error", {
                            "request_id": request_id,
                            "prompt": prompt,
                            "error": str(e),
                            "mode": "multi",
                            "pipeline": "unified",
                        })
            
            # Run in background thread
            threading.Thread(target=run_pipeline, daemon=True, name="PipelineExecutor").start()
            
        except Exception as e:
            logger.error(f"Pipeline creation failed: {e}", exc_info=True)
            if HAS_PYQT6 and hasattr(self, "image_label"):
                self.image_label.setText(f"❌ Unified pipeline creation failed\n{e}")
            if self.event_bus:
                self.event_bus.publish("visual.generation.error", {
                    "request_id": request_id,
                    "prompt": prompt,
                    "error": str(e),
                    "mode": "multi",
                    "pipeline": "unified",
                })
    
    def _display_pipeline_result(self, result: Any):
        """Display result from multi-engine pipeline."""
        try:
            final_output = result.final_output
            
            if isinstance(final_output, dict):
                output_type = final_output.get('type', 'unknown')
                
                if output_type == 'image' and 'path' in final_output:
                    self.display_image(final_output['path'])
                
                elif output_type == 'video' and 'path' in final_output:
                    self._display_video_result(final_output['path'], result.pipeline_id, result.metadata.get('original_request', ''))
                
                elif output_type in ['3d_model', 'unity_scene']:
                    # Display info about 3D output
                    if HAS_PYQT6:
                        self.image_label.setText(f"✅ 3D Creation Complete\n\nType: {output_type}\nTime: {result.execution_time:.2f}s")
                        self.image_label.setStyleSheet("""
                            QLabel {
                                background-color: #1e1e1e;
                                border: 2px solid #28a745;
                                border-radius: 8px;
                                color: #28a745;
                            }
                        """)
                else:
                    logger.info(f"Pipeline result type: {output_type}")
            else:
                logger.warning(f"Unknown pipeline result format: {type(final_output)}")
        
        except Exception as e:
            logger.error(f"Error displaying pipeline result: {e}", exc_info=True)
    
    def display_image(self, image_path: str):
        """Display image on canvas."""
        if not HAS_PYQT6:
            return
        
        if not Path(image_path).exists():
            logger.error(f"Image file not found: {image_path}")
            return
        
        # Stop any video playback and switch to image view
        if self._video_player:
            self._video_player.stop()
        self._display_stack.setCurrentWidget(self.image_label)
        
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
            self._last_displayed_image = image_path
            
    
    def closeEvent(self, event):
        """Cleanup on close."""
        self._cleanup_threads()
        self._cleanup_video_player()
        if HAS_PYQT6:
            super().closeEvent(event)
    
    def _cleanup_video_player(self):
        """Clean up video player resources."""
        try:
            if self._video_player:
                self._video_player.cleanup()
                logger.info("✅ Video player cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up video player: {e}")
    
    def _cleanup_threads(self):
        """Clean up QThread instances to prevent 'QThread destroyed while running' errors."""
        try:
            if HAS_PYQT6 and self._worker_thread and self._worker_thread.isRunning():
                self._worker_thread.requestInterruption()
                self._worker_thread.quit()
                if not self._worker_thread.wait(3000):
                    logger.warning("VisualCreationCanvas worker thread did not stop in time, terminating")
                    self._worker_thread.terminate()
                    self._worker_thread.wait(1000)
            if self._worker:
                try:
                    self._worker.deleteLater()
                except Exception:
                    pass
            logger.info("VisualCreationCanvas threads cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up VisualCreationCanvas threads: {e}")
