"""
SOTA 2026 Production Video Generation Backends
Implements Mochi 1, SVD-XT, HunyuanVideo, LTXVideo, CogVideoX, and AnimateLCM
for grandeur-level quality video generation.

Backend Summary:
- Mochi 1: 10B params, 848x480, 84 frames, production quality
- CogVideoX: 5B params, 768x1360, 10s video, 3D attention
- LTXVideo: Real-time, 1216x704, 30fps
- HunyuanVideo: 13B params, 1080p cinematic (60GB+ VRAM)
- SVD-XT: Image-to-video, 1024x576, 25 frames
- AnimateLCM: Fast animation, 4-step generation
"""

import os
import time
import logging
from typing import List, Optional, Tuple
from PIL import Image

# Safe PyTorch import with DLL error handling
torch = None
torch_available = False
try:
    import torch
    # Test if PyTorch can be used without DLL errors
    _ = torch.tensor([1, 2, 3])
    torch_available = True
except Exception as torch_error:
    logging.warning(f"PyTorch import failed: {torch_error}")
    logging.warning("Video backends will be disabled due to PyTorch DLL issues")

logger = logging.getLogger("KingdomAI.VideoBackends")


class Mochi1Backend:
    """Mochi 1 (Genmo) - 10B parameter production video generation."""
    
    def __init__(self, cuda_available: bool = True):
        self.pipe = None
        self.cuda_available = cuda_available and torch_available
        self.variant = None
        
    def load_pipeline(self, variant: str = "bf16"):
        """Load Mochi 1 pipeline with memory optimization."""
        if not torch_available:
            logger.warning("PyTorch not available - Mochi 1 backend disabled")
            return None
            
        if self.pipe is not None and self.variant == variant:
            return self.pipe
            
        try:
            from diffusers import MochiPipeline
            
            dtype = torch.bfloat16 if variant == "bf16" else torch.float16
            
            logger.info(f"🎬 Loading Mochi 1 ({variant} variant)...")
            self.pipe = MochiPipeline.from_pretrained(
                "genmo/mochi-1-preview",
                variant=variant,
                torch_dtype=dtype
            )
            
            # Enable memory optimizations
            self.pipe.enable_model_cpu_offload()
            self.pipe.enable_vae_tiling()
            
            self.variant = variant
            logger.info("✅ Mochi 1 pipeline loaded successfully")
            return self.pipe
            
        except Exception as e:
            logger.error(f"Failed to load Mochi 1 pipeline: {e}")
            return None
    
    def generate(self, prompt: str, num_frames: int = 85, num_steps: int = 64,
                 guidance_scale: float = 4.5, seed: int = -1) -> List[Image.Image]:
        """Generate video with Mochi 1 - production quality."""
        pipe = self.load_pipeline()
        
        if seed <= 0:
            seed = int(time.time() * 1000) % 2147483647
        
        logger.info(f"🎬 Mochi 1 generating: {num_frames} frames, {num_steps} steps")
        
        with torch.autocast("cuda", torch.bfloat16, cache_enabled=False):
            result = pipe(
                prompt=prompt,
                num_frames=num_frames,
                num_inference_steps=num_steps,
                guidance_scale=guidance_scale,
                generator=torch.Generator("cuda").manual_seed(seed)
            )
        
        return result.frames[0]  # type: ignore[attr-defined]


class SVDXTBackend:
    """Stable Video Diffusion XT - High-res image-to-video."""
    
    def __init__(self, cuda_available: bool = True):
        self.pipe = None
        self.cuda_available = cuda_available
        
    def load_pipeline(self):
        """Load SVD-XT pipeline."""
        if self.pipe is not None:
            return self.pipe
            
        try:
            from diffusers import StableVideoDiffusionPipeline
            
            logger.info("🎬 Loading Stable Video Diffusion XT...")
            self.pipe = StableVideoDiffusionPipeline.from_pretrained(
                "stabilityai/stable-video-diffusion-img2vid-xt",
                torch_dtype=torch.float16,
                variant="fp16"
            )
            
            self.pipe.enable_model_cpu_offload()
            
            logger.info("✅ SVD-XT pipeline loaded successfully")
            return self.pipe
            
        except Exception as e:
            logger.error(f"Failed to load SVD-XT: {e}")
            raise
    
    def generate_from_image(self, image: Image.Image, num_frames: int = 25,
                           fps: int = 7, motion_bucket_id: int = 127,
                           noise_aug_strength: float = 0.02, seed: int = -1) -> List[Image.Image]:
        """Generate video from image with SVD-XT - 1024x576 quality."""
        pipe = self.load_pipeline()
        
        # Resize image to SVD-XT optimal resolution
        image = image.resize((1024, 576))
        
        if seed <= 0:
            seed = int(time.time() * 1000) % 2147483647
        
        generator = torch.Generator("cuda").manual_seed(seed)
        
        logger.info(f"🎬 SVD-XT generating: {num_frames} frames from image")
        
        result = pipe(
            image=image,
            decode_chunk_size=8,
            generator=generator,
            num_frames=num_frames,
            motion_bucket_id=motion_bucket_id,
            noise_aug_strength=noise_aug_strength,
            fps=fps
        )
        
        return result.frames[0]  # type: ignore[attr-defined]


class HunyuanVideoBackend:
    """HunyuanVideo (Tencent) - 13B parameter cinematic 1080p generation."""
    
    def __init__(self, cuda_available: bool = True):
        self.pipe = None
        self.cuda_available = cuda_available
        
    def load_pipeline(self):
        """Load HunyuanVideo pipeline (requires separate installation)."""
        if self.pipe is not None:
            return self.pipe
            
        try:
            # HunyuanVideo uses custom pipeline from their repo
            import hunyuan_video
            from hunyuan_video.pipeline import HunyuanVideoPipeline
            
            logger.info("🎬 Loading HunyuanVideo (13B params)...")
            self.pipe = HunyuanVideoPipeline.from_pretrained(
                "tencent/HunyuanVideo",
                torch_dtype=torch.float16
            )
            
            self.pipe.enable_model_cpu_offload()
            
            logger.info("✅ HunyuanVideo pipeline loaded successfully")
            return self.pipe
            
        except Exception as e:
            logger.error(f"Failed to load HunyuanVideo: {e}")
            raise
    
    def generate(self, prompt: str, width: int = 1280, height: int = 720,
                 num_frames: int = 129, num_steps: int = 50,
                 guidance_scale: float = 6.0, seed: int = -1) -> List[Image.Image]:
        """Generate cinematic video with HunyuanVideo - 720p-1080p quality."""
        pipe = self.load_pipeline()
        
        if seed <= 0:
            seed = int(time.time() * 1000) % 2147483647
        
        logger.info(f"🎬 HunyuanVideo generating: {width}x{height}, {num_frames} frames")
        
        result = pipe(
            prompt=prompt,
            height=height,
            width=width,
            num_frames=num_frames,
            num_inference_steps=num_steps,
            guidance_scale=guidance_scale,
            generator=torch.Generator("cuda").manual_seed(seed)
        )
        
        return result.frames[0]  # type: ignore[attr-defined]


class LTXVideoBackend:
    """LTXVideo (Lightricks) - Real-time video generation."""
    
    def __init__(self, cuda_available: bool = True):
        self.pipe = None
        self.cuda_available = cuda_available
        
    def load_pipeline(self):
        """Load LTXVideo pipeline."""
        if self.pipe is not None:
            return self.pipe
            
        try:
            from diffusers import LTXPipeline
            
            logger.info("🎬 Loading LTXVideo (real-time)...")
            self.pipe = LTXPipeline.from_pretrained(
                "Lightricks/LTX-Video",
                torch_dtype=torch.float16
            )
            
            self.pipe.enable_model_cpu_offload()
            
            logger.info("✅ LTXVideo pipeline loaded successfully")
            return self.pipe
            
        except Exception as e:
            logger.error(f"Failed to load LTXVideo: {e}")
            raise
    
    def generate(self, prompt: str, num_frames: int = 24, num_steps: int = 8,
                 guidance_scale: float = 3.0, seed: int = -1) -> List[Image.Image]:
        """Generate video with LTXVideo - real-time 768x512."""
        pipe = self.load_pipeline()
        
        if seed <= 0:
            seed = int(time.time() * 1000) % 2147483647
        
        logger.info(f"🎬 LTXVideo generating: {num_frames} frames (real-time)")
        
        result = pipe(
            prompt=prompt,
            num_frames=num_frames,
            num_inference_steps=num_steps,
            guidance_scale=guidance_scale,
            generator=torch.Generator("cuda").manual_seed(seed)
        )
        
        return result.frames[0]  # type: ignore[attr-defined]


class CogVideoXBackend:
    """
    CogVideoX - SOTA 2026 5B parameter text-to-video with 3D attention.
    
    Features:
    - 3D Causal VAE: Compresses video spatially and temporally
    - Expert Transformer: Adaptive LayerNorm for text-video alignment
    - 3D Full Attention: Captures motion and temporal dynamics
    - Output: 768x1360 resolution, 10s video at 16fps
    - VRAM: ~16GB with quantization
    """
    
    def __init__(self, cuda_available: bool = True):
        self.pipe = None
        self.cuda_available = cuda_available and torch_available
        self.quantized = False
        
    def load_pipeline(self, use_quantization: bool = True):
        """Load CogVideoX pipeline with optional quantization for lower VRAM."""
        if not torch_available:
            logger.warning("PyTorch not available - CogVideoX backend disabled")
            return None
            
        if self.pipe is not None:
            return self.pipe
            
        try:
            from diffusers import CogVideoXPipeline
            
            logger.info("🎬 Loading CogVideoX (5B params)...")
            
            # Load with bfloat16 for better quality
            self.pipe = CogVideoXPipeline.from_pretrained(
                "THUDM/CogVideoX-5b",
                torch_dtype=torch.bfloat16
            )
            
            # Enable memory optimizations
            self.pipe.enable_model_cpu_offload()
            
            # Optional: Enable VAE slicing for lower memory
            try:
                self.pipe.enable_vae_slicing()
            except AttributeError:
                pass
            
            # Optional: Enable VAE tiling
            try:
                self.pipe.enable_vae_tiling()
            except AttributeError:
                pass
            
            logger.info("✅ CogVideoX pipeline loaded successfully")
            return self.pipe
            
        except ImportError as e:
            logger.error(f"CogVideoX not available - install: pip install diffusers>=0.30.0")
            logger.error(f"Import error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load CogVideoX pipeline: {e}")
            return None
    
    def generate(self, prompt: str, num_frames: int = 49, num_steps: int = 50,
                 guidance_scale: float = 6.0, width: int = 720, height: int = 480,
                 seed: int = -1) -> Optional[List[Image.Image]]:
        """
        Generate video with CogVideoX - high quality text-to-video.
        
        Args:
            prompt: Text description of the video
            num_frames: Number of frames (default 49 for ~3s at 16fps)
            num_steps: Inference steps (default 50)
            guidance_scale: CFG scale (default 6.0)
            width: Video width (default 720)
            height: Video height (default 480)
            seed: Random seed (-1 for random)
            
        Returns:
            List of PIL Images representing video frames
        """
        pipe = self.load_pipeline()
        if pipe is None:
            return None
        
        if seed <= 0:
            seed = int(time.time() * 1000) % 2147483647
        
        logger.info(f"🎬 CogVideoX generating: {width}x{height}, {num_frames} frames, {num_steps} steps")
        
        try:
            with torch.inference_mode():
                result = pipe(
                    prompt=prompt,
                    num_frames=num_frames,
                    num_inference_steps=num_steps,
                    guidance_scale=guidance_scale,
                    width=width,
                    height=height,
                    generator=torch.Generator("cuda").manual_seed(seed) if self.cuda_available else None
                )
            
            logger.info(f"✅ CogVideoX generation complete: {len(result.frames[0])} frames")
            return result.frames[0]
            
        except Exception as e:
            logger.error(f"CogVideoX generation failed: {e}")
            return None


class AnimateLCMBackend:
    """
    AnimateLCM - SOTA 2026 Fast Animation Generation.
    
    Features:
    - LCM distillation for 4-step generation
    - Compatible with existing SD checkpoints and LoRAs
    - Text-to-video and image-to-video support
    - Decoupled consistency learning for quality
    """
    
    def __init__(self, cuda_available: bool = True):
        self.pipe = None
        self.cuda_available = cuda_available and torch_available
        
    def load_pipeline(self, base_model: str = "emilianJR/epiCRealism"):
        """Load AnimateLCM pipeline."""
        if not torch_available:
            logger.warning("PyTorch not available - AnimateLCM backend disabled")
            return None
            
        if self.pipe is not None:
            return self.pipe
            
        try:
            from diffusers import AnimateDiffPipeline, LCMScheduler, MotionAdapter
            
            logger.info("🎬 Loading AnimateLCM...")
            
            # Load motion adapter
            adapter = MotionAdapter.from_pretrained(
                "wangfuyun/AnimateLCM",
                torch_dtype=torch.float16
            )
            
            # Load base pipeline with adapter
            self.pipe = AnimateDiffPipeline.from_pretrained(
                base_model,
                motion_adapter=adapter,
                torch_dtype=torch.float16
            )
            
            # Set LCM scheduler for fast generation
            self.pipe.scheduler = LCMScheduler.from_config(self.pipe.scheduler.config)
            
            # Enable memory optimizations
            self.pipe.enable_model_cpu_offload()
            
            logger.info("✅ AnimateLCM pipeline loaded successfully")
            return self.pipe
            
        except ImportError as e:
            logger.error(f"AnimateLCM not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load AnimateLCM pipeline: {e}")
            return None
    
    def generate(self, prompt: str, num_frames: int = 16, num_steps: int = 4,
                 guidance_scale: float = 1.5, width: int = 512, height: int = 512,
                 seed: int = -1) -> Optional[List[Image.Image]]:
        """
        Generate animation with AnimateLCM - fast 4-step generation.
        
        Args:
            prompt: Text description
            num_frames: Number of frames (default 16)
            num_steps: Inference steps (default 4 - LCM optimized)
            guidance_scale: CFG scale (default 1.5 for LCM)
            width: Video width
            height: Video height
            seed: Random seed
            
        Returns:
            List of PIL Images representing animation frames
        """
        pipe = self.load_pipeline()
        if pipe is None:
            return None
        
        if seed <= 0:
            seed = int(time.time() * 1000) % 2147483647
        
        logger.info(f"🎬 AnimateLCM generating: {width}x{height}, {num_frames} frames, {num_steps} steps (fast)")
        
        try:
            result = pipe(
                prompt=prompt,
                num_frames=num_frames,
                num_inference_steps=num_steps,
                guidance_scale=guidance_scale,
                width=width,
                height=height,
                generator=torch.Generator("cuda").manual_seed(seed) if self.cuda_available else None
            )
            
            logger.info(f"✅ AnimateLCM generation complete: {len(result.frames[0])} frames")
            return result.frames[0]
            
        except Exception as e:
            logger.error(f"AnimateLCM generation failed: {e}")
            return None


def get_available_video_backends() -> dict:
    """
    Check and return available video generation backends.
    
    Returns dict with backend availability status.
    """
    backends = {
        'mochi1': False,
        'cogvideox': False,
        'ltxvideo': False,
        'hunyuan': False,
        'svd_xt': False,
        'animatelcm': False
    }
    
    if not torch_available:
        logger.warning("PyTorch not available - all video backends disabled")
        return backends
    
    # Check each backend
    try:
        from diffusers import MochiPipeline
        backends['mochi1'] = True
    except ImportError:
        pass
    
    try:
        from diffusers import CogVideoXPipeline
        backends['cogvideox'] = True
    except ImportError:
        pass
    
    try:
        from diffusers import LTXPipeline
        backends['ltxvideo'] = True
    except ImportError:
        pass
    
    try:
        from diffusers import StableVideoDiffusionPipeline
        backends['svd_xt'] = True
    except ImportError:
        pass
    
    try:
        from diffusers import AnimateDiffPipeline, MotionAdapter
        backends['animatelcm'] = True
    except ImportError:
        pass
    
    # HunyuanVideo requires separate installation
    try:
        import hunyuan_video
        backends['hunyuan'] = True
    except ImportError:
        pass
    
    return backends


def apply_quality_preset(config, preset: str):
    """Apply quality preset to generation config - SOTA 2026."""
    presets = {
        'draft': {
            'steps': 6,
            'width': 512,
            'height': 512,
            'guidance_scale': 2.0,
            'num_frames': 16
        },
        'standard': {
            'steps': 12,
            'width': 768,
            'height': 512,
            'guidance_scale': 7.5,
            'num_frames': 24
        },
        'production': {
            'steps': 30,
            'width': 1024,
            'height': 576,
            'guidance_scale': 8.0,
            'num_frames': 48
        },
        'cinematic': {
            'steps': 64,
            'width': 1280,
            'height': 720,
            'guidance_scale': 6.0,
            'num_frames': 129
        }
    }
    
    if preset in presets:
        settings = presets[preset]
        for key, value in settings.items():
            if hasattr(config, key):
                setattr(config, key, value)
        logger.info(f"✅ Applied {preset.upper()} quality preset")
    
    return config
