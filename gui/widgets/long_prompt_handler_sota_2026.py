"""
SOTA 2026 Long Prompt Handler with Weighted Embeddings
Handles prompts of ANY length using sd_embed library for weighted text embeddings
Supports Stable Diffusion 1.5, SDXL, AnimateDiff, and all diffusers pipelines
"""

import logging
from typing import Tuple, Optional, Any

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
    logging.warning("Long prompt handler will be disabled due to PyTorch DLL issues")

# Define fallback type hints
if torch_available:
    TensorType = torch.Tensor
else:
    TensorType = Any

logger = logging.getLogger("KingdomAI.LongPromptHandler")


class LongPromptHandler:
    """SOTA 2026: Handle prompts of unlimited length with weighted embeddings."""
    
    def __init__(self, pipeline, model_type: str = "sd15"):
        """
        Initialize long prompt handler.
        
        Args:
            pipeline: Diffusers pipeline (AnimateDiffPipeline, StableDiffusionPipeline, etc.)
            model_type: "sd15", "sdxl", "sd3", or "flux"
        """
        self.pipeline = pipeline
        self.model_type = model_type
        self._sd_embed_available = False
        
        try:
            from sd_embed.embedding_funcs import (
                get_weighted_text_embeddings_sd15,
                get_weighted_text_embeddings_sdxl,
                get_weighted_text_embeddings_sd3,
                get_weighted_text_embeddings_flux1
            )
            self._sd_embed_available = True
            self._embed_funcs = {
                "sd15": get_weighted_text_embeddings_sd15,
                "sdxl": get_weighted_text_embeddings_sdxl,
                "sd3": get_weighted_text_embeddings_sd3,
                "flux": get_weighted_text_embeddings_flux1
            }
            logger.info("✅ sd_embed library available for long prompt handling")
        except ImportError:
            logger.warning("⚠️ sd_embed not available - install: pip install git+https://github.com/xhinker/sd_embed.git@main")
    
    def process_prompt(
        self,
        prompt: str,
        negative_prompt: str = ""
    ) -> Tuple[TensorType, Optional[TensorType], Optional[TensorType], Optional[TensorType]]:
        """
        Process prompt of ANY length and return weighted embeddings.
        
        Returns:
            For SD 1.5: (prompt_embeds, negative_prompt_embeds, None, None)
            For SDXL: (prompt_embeds, negative_prompt_embeds, pooled_embeds, negative_pooled_embeds)
        """
        if not self._sd_embed_available:
            logger.warning("sd_embed not available, prompt will be truncated to 77 tokens")
            return None, None, None, None
        
        try:
            embed_func = self._embed_funcs.get(self.model_type)
            if not embed_func:
                logger.error(f"Unknown model type: {self.model_type}")
                return None, None, None, None
            
            logger.info(f"🎨 Processing long prompt with sd_embed ({self.model_type})")
            
            if self.model_type == "sd15":
                # SD 1.5 / AnimateDiff
                prompt_embeds, negative_prompt_embeds = embed_func(
                    pipe=self.pipeline,
                    prompt=prompt,
                    neg_prompt=negative_prompt
                )
                return prompt_embeds, negative_prompt_embeds, None, None
                
            elif self.model_type == "sdxl":
                # SDXL
                (
                    prompt_embeds,
                    negative_prompt_embeds,
                    pooled_prompt_embeds,
                    negative_pooled_prompt_embeds
                ) = embed_func(
                    pipe=self.pipeline,
                    prompt=prompt,
                    neg_prompt=negative_prompt
                )
                return prompt_embeds, negative_prompt_embeds, pooled_prompt_embeds, negative_pooled_prompt_embeds
                
            elif self.model_type == "flux":
                # Flux
                prompt_embeds, pooled_prompt_embeds = embed_func(
                    pipe=self.pipeline,
                    prompt=prompt
                )
                return prompt_embeds, None, pooled_prompt_embeds, None
                
            else:
                logger.warning(f"Model type {self.model_type} not fully supported yet")
                return None, None, None, None
                
        except Exception as e:
            logger.error(f"Long prompt processing failed: {e}")
            return None, None, None, None
    
    @staticmethod
    def is_available() -> bool:
        """Check if sd_embed library is available."""
        try:
            import sd_embed
            return True
        except ImportError:
            return False


def install_sd_embed():
    """Install sd_embed library for long prompt support."""
    import subprocess
    import sys
    
    logger.info("📦 Installing sd_embed library...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "git+https://github.com/xhinker/sd_embed.git@main"
        ])
        logger.info("✅ sd_embed installed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to install sd_embed: {e}")
        return False
