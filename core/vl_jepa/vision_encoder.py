"""
Vision Encoder for VL-JEPA
===========================

Encodes visual inputs (images, video frames) into continuous embeddings.
Based on V-JEPA 2 architecture from Meta FAIR.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Union, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class VisionEncoder(nn.Module):
    """
    Vision encoder that processes visual inputs into continuous embeddings.
    Uses Vision Transformer (ViT) architecture with JEPA-style masking.
    """
    
    def __init__(
        self,
        image_size: int = 224,
        patch_size: int = 16,
        num_channels: int = 3,
        embed_dim: int = 768,
        depth: int = 12,
        num_heads: int = 12,
        mlp_ratio: float = 4.0,
        dropout: float = 0.1,
        output_dim: int = 768,
        device: torch.device = torch.device('cpu')
    ):
        super().__init__()
        
        self.image_size = image_size
        self.patch_size = patch_size
        self.num_patches = (image_size // patch_size) ** 2
        self.embed_dim = embed_dim
        self.output_dim = output_dim  # Store output dimension
        self.device = device
        
        # Patch embedding
        self.patch_embed = nn.Conv2d(
            num_channels, embed_dim, 
            kernel_size=patch_size, stride=patch_size
        )
        
        # Position embedding
        self.pos_embed = nn.Parameter(
            torch.zeros(1, self.num_patches + 1, embed_dim)
        )
        
        # CLS token
        self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
        
        # Transformer blocks
        self.blocks = nn.ModuleList([
            TransformerBlock(
                dim=embed_dim,
                num_heads=num_heads,
                mlp_ratio=mlp_ratio,
                dropout=dropout
            )
            for _ in range(depth)
        ])
        
        # Output projection
        self.norm = nn.LayerNorm(embed_dim)
        self.head = nn.Linear(embed_dim, output_dim)
        
        # Initialize weights
        self._init_weights()
        
        # Move to device
        self.to(device)
        
        logger.info(f"Vision encoder initialized with {depth} layers, {num_heads} heads")
    
    def _init_weights(self):
        """Initialize weights using JEPA-style initialization"""
        # Initialize patch embedding
        nn.init.xavier_uniform_(self.patch_embed.weight)
        
        # Initialize position embedding
        nn.init.normal_(self.pos_embed, std=0.02)
        
        # Initialize CLS token
        nn.init.normal_(self.cls_token, std=0.02)
        
        # Initialize output head
        nn.init.xavier_uniform_(self.head.weight)
        nn.init.zeros_(self.head.bias)
    
    async def encode(
        self, 
        vision_input: Union[torch.Tensor, np.ndarray, Dict[str, Any]]
    ) -> torch.Tensor:
        """
        Encode visual input to continuous embedding.
        
        Args:
            vision_input: Image tensor, numpy array, or dict with 'image' key
            
        Returns:
            Continuous embedding tensor
        """
        try:
            # Extract image tensor
            if isinstance(vision_input, dict):
                image = vision_input.get('image') or vision_input.get('frame')
                if image is None:
                    return torch.zeros(self.output_dim, device=self.device)
            else:
                image = vision_input
            
            # Convert to tensor if needed
            if isinstance(image, np.ndarray):
                image = torch.from_numpy(image).float()
            
            # Ensure correct shape (B, C, H, W)
            if len(image.shape) == 3:
                image = image.unsqueeze(0)  # Add batch dimension
            
            # Move to device
            image = image.to(self.device)
            
            # Resize if needed
            if image.shape[-2:] != (self.image_size, self.image_size):
                image = F.interpolate(
                    image, 
                    size=(self.image_size, self.image_size),
                    mode='bilinear',
                    align_corners=False
                )
            
            # Forward pass
            embedding = self.forward(image)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error encoding vision input: {e}")
            return torch.zeros(self.output_dim, device=self.device)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass through vision encoder"""
        B = x.shape[0]
        
        # Patch embedding
        x = self.patch_embed(x)  # (B, embed_dim, H', W')
        x = x.flatten(2).transpose(1, 2)  # (B, num_patches, embed_dim)
        
        # Add CLS token
        cls_tokens = self.cls_token.expand(B, -1, -1)
        x = torch.cat((cls_tokens, x), dim=1)
        
        # Add position embedding
        x = x + self.pos_embed[:, :x.size(1), :]
        
        # Apply transformer blocks
        for block in self.blocks:
            x = block(x)
        
        # Final norm and projection
        x = self.norm(x)
        
        # Use CLS token as output
        cls_output = x[:, 0]
        
        # Project to output dimension
        output = self.head(cls_output)
        
        return output
    
    def extract_features(
        self, 
        x: torch.Tensor,
        layer_indices: Optional[List[int]] = None
    ) -> Dict[str, torch.Tensor]:
        """
        Extract intermediate features from specified layers.
        Useful for multi-scale representation learning.
        """
        if layer_indices is None:
            layer_indices = [3, 6, 9, 11]  # Default to 4 scales
        
        features = {}
        B = x.shape[0]
        
        # Patch embedding
        x = self.patch_embed(x)
        x = x.flatten(2).transpose(1, 2)
        
        # Add CLS token
        cls_tokens = self.cls_token.expand(B, -1, -1)
        x = torch.cat((cls_tokens, x), dim=1)
        
        # Add position embedding
        x = x + self.pos_embed[:, :x.size(1), :]
        
        # Extract features at specified layers
        for i, block in enumerate(self.blocks):
            x = block(x)
            if i in layer_indices:
                features[f'layer_{i}'] = x.clone()
        
        # Final features
        x = self.norm(x)
        features['final'] = x
        
        return features


class TransformerBlock(nn.Module):
    """Single transformer block with self-attention and MLP"""
    
    def __init__(
        self,
        dim: int,
        num_heads: int,
        mlp_ratio: float = 4.0,
        dropout: float = 0.1
    ):
        super().__init__()
        
        self.norm1 = nn.LayerNorm(dim)
        self.attn = nn.MultiheadAttention(
            dim, num_heads, dropout=dropout, batch_first=True
        )
        
        self.norm2 = nn.LayerNorm(dim)
        mlp_hidden_dim = int(dim * mlp_ratio)
        self.mlp = nn.Sequential(
            nn.Linear(dim, mlp_hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(mlp_hidden_dim, dim),
            nn.Dropout(dropout)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Self-attention
        x_norm = self.norm1(x)
        attn_out, _ = self.attn(x_norm, x_norm, x_norm)
        x = x + attn_out
        
        # MLP
        x = x + self.mlp(self.norm2(x))
        
        return x


class VisionPreprocessor:
    """Preprocessor for various vision input formats"""
    
    @staticmethod
    def preprocess_image(image: Union[np.ndarray, torch.Tensor]) -> torch.Tensor:
        """Preprocess image for vision encoder"""
        if isinstance(image, np.ndarray):
            # Convert from numpy
            image = torch.from_numpy(image).float()
        
        # Normalize to [0, 1]
        if image.max() > 1.0:
            image = image / 255.0
        
        # Ensure channel-first format
        if len(image.shape) == 3 and image.shape[-1] in [1, 3]:
            image = image.permute(2, 0, 1)
        
        # Normalize using ImageNet stats
        mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
        
        if image.shape[0] == 3:
            image = (image - mean) / std
        
        return image
    
    @staticmethod
    def extract_frames(video: np.ndarray, num_frames: int = 8) -> List[torch.Tensor]:
        """Extract frames from video for processing"""
        frames = []
        
        total_frames = video.shape[0] if len(video.shape) == 4 else 1
        indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
        
        for idx in indices:
            frame = video[idx] if len(video.shape) == 4 else video
            processed = VisionPreprocessor.preprocess_image(frame)
            frames.append(processed)
        
        return frames
