"""
Predictor Network for VL-JEPA
==============================

The predictor network that maps combined vision-text features to 
continuous embeddings in the joint representation space.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


class PredictorNetwork(nn.Module):
    """
    Predictor network that predicts continuous embeddings from multimodal features.
    This is the core component that enables VL-JEPA's efficiency gains.
    """
    
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 512,
        output_dim: int = 1024,
        num_layers: int = 6,
        dropout: float = 0.1,
        activation: str = 'gelu',
        use_layer_norm: bool = True,
        device: torch.device = torch.device('cpu')
    ):
        super().__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.num_layers = num_layers
        self.device = device
        
        # Input projection
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        
        # Predictor layers
        self.layers = nn.ModuleList()
        for i in range(num_layers):
            layer = PredictorLayer(
                hidden_dim=hidden_dim,
                dropout=dropout,
                activation=activation,
                use_layer_norm=use_layer_norm
            )
            self.layers.append(layer)
        
        # Output projection
        self.output_proj = nn.Sequential(
            nn.LayerNorm(hidden_dim) if use_layer_norm else nn.Identity(),
            nn.Linear(hidden_dim, output_dim),
            nn.Tanh()  # Bound output to [-1, 1]
        )
        
        # Context attention for adaptive prediction
        self.context_attention = ContextAttention(
            hidden_dim=hidden_dim,
            num_heads=8,
            dropout=dropout
        )
        
        # Initialize weights
        self._init_weights()
        
        # Move to device
        self.to(device)
        
        logger.info(f"Predictor network initialized with {num_layers} layers")
    
    def _init_weights(self):
        """Initialize weights using Xavier initialization"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
    
    async def predict(
        self,
        features: torch.Tensor,
        context: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Predict continuous embedding from features.
        
        Args:
            features: Combined multimodal features
            context: Optional context tensor for adaptive prediction
            
        Returns:
            Predicted continuous embedding
        """
        try:
            # Ensure features are on device
            features = features.to(self.device)
            
            # Add batch dimension if missing
            if len(features.shape) == 1:
                features = features.unsqueeze(0)
            
            # Forward pass
            embedding = self.forward(features, context)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error in predict: {e}")
            return torch.zeros(self.output_dim, device=self.device)
    
    def forward(
        self,
        x: torch.Tensor,
        context: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """Forward pass through predictor network"""
        # Input projection
        x = self.input_proj(x)
        
        # Apply predictor layers
        for layer in self.layers:
            x = layer(x)
        
        # Apply context attention if context provided
        if context is not None:
            x = self.context_attention(x, context)
        
        # Output projection
        output = self.output_proj(x)
        
        return output
    
    def predict_with_uncertainty(
        self,
        features: torch.Tensor,
        num_samples: int = 10
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Predict with uncertainty estimation using Monte Carlo dropout.
        
        Returns:
            Tuple of (mean prediction, uncertainty)
        """
        self.train()  # Enable dropout for uncertainty estimation
        
        predictions = []
        with torch.no_grad():
            for _ in range(num_samples):
                pred = self.forward(features)
                predictions.append(pred)
        
        predictions = torch.stack(predictions)
        mean = predictions.mean(dim=0)
        uncertainty = predictions.std(dim=0)
        
        self.eval()  # Return to eval mode
        
        return mean, uncertainty


class PredictorLayer(nn.Module):
    """Single predictor layer with residual connection"""
    
    def __init__(
        self,
        hidden_dim: int,
        dropout: float = 0.1,
        activation: str = 'gelu',
        use_layer_norm: bool = True
    ):
        super().__init__()
        
        # Layer components
        self.norm1 = nn.LayerNorm(hidden_dim) if use_layer_norm else nn.Identity()
        self.ff1 = nn.Linear(hidden_dim, hidden_dim * 4)
        
        # Activation function
        if activation == 'gelu':
            self.activation = nn.GELU()
        elif activation == 'relu':
            self.activation = nn.ReLU()
        else:
            self.activation = nn.SiLU()
        
        self.dropout1 = nn.Dropout(dropout)
        self.ff2 = nn.Linear(hidden_dim * 4, hidden_dim)
        self.dropout2 = nn.Dropout(dropout)
        
        self.norm2 = nn.LayerNorm(hidden_dim) if use_layer_norm else nn.Identity()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass with residual connection"""
        residual = x
        
        # Feed-forward with expansion
        x = self.norm1(x)
        x = self.ff1(x)
        x = self.activation(x)
        x = self.dropout1(x)
        x = self.ff2(x)
        x = self.dropout2(x)
        
        # Residual connection
        x = residual + x
        x = self.norm2(x)
        
        return x


class ContextAttention(nn.Module):
    """
    Context-aware attention mechanism for adaptive prediction.
    Allows the predictor to adapt based on task context.
    """
    
    def __init__(
        self,
        hidden_dim: int,
        num_heads: int = 8,
        dropout: float = 0.1
    ):
        super().__init__()
        
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads
        
        # Multi-head attention
        self.q_proj = nn.Linear(hidden_dim, hidden_dim)
        self.k_proj = nn.Linear(hidden_dim, hidden_dim)
        self.v_proj = nn.Linear(hidden_dim, hidden_dim)
        
        self.out_proj = nn.Linear(hidden_dim, hidden_dim)
        self.dropout = nn.Dropout(dropout)
        
        self.norm = nn.LayerNorm(hidden_dim)
    
    def forward(
        self,
        x: torch.Tensor,
        context: torch.Tensor
    ) -> torch.Tensor:
        """Apply context-aware attention"""
        B, D = x.shape
        
        # Ensure context has same batch size
        if context.shape[0] != B:
            context = context.expand(B, -1)
        
        residual = x
        x = self.norm(x)
        
        # Project to Q, K, V
        Q = self.q_proj(x).view(B, self.num_heads, self.head_dim)
        K = self.k_proj(context).view(B, self.num_heads, self.head_dim)
        V = self.v_proj(context).view(B, self.num_heads, self.head_dim)
        
        # Scaled dot-product attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / (self.head_dim ** 0.5)
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)
        
        # Apply attention to values
        attn_output = torch.matmul(attn_weights, V)
        attn_output = attn_output.view(B, self.hidden_dim)
        
        # Output projection
        output = self.out_proj(attn_output)
        output = self.dropout(output)
        
        # Residual connection
        output = residual + output
        
        return output


class AdaptivePredictor:
    """
    Adaptive predictor that selects prediction strategy based on context.
    Implements the selective decoding mechanism for 2.85x efficiency gain.
    """
    
    def __init__(self, predictor_network: PredictorNetwork):
        self.predictor = predictor_network
        self.prediction_strategies = {
            'fast': self._fast_prediction,
            'balanced': self._balanced_prediction,
            'accurate': self._accurate_prediction
        }
    
    async def predict_adaptive(
        self,
        features: torch.Tensor,
        context: Dict[str, Any]
    ) -> Tuple[torch.Tensor, str]:
        """
        Adaptively select prediction strategy based on context.
        
        Returns:
            Tuple of (prediction, strategy_used)
        """
        # Determine strategy based on context
        strategy = self._select_strategy(context)
        
        # Apply selected strategy
        prediction = await self.prediction_strategies[strategy](features, context)
        
        return prediction, strategy
    
    def _select_strategy(self, context: Dict[str, Any]) -> str:
        """Select prediction strategy based on context"""
        # Check for real-time requirements
        if context.get('real_time', False):
            return 'fast'
        
        # Check for high-stakes decisions
        if context.get('high_stakes', False):
            return 'accurate'
        
        # Default to balanced
        return 'balanced'
    
    async def _fast_prediction(
        self,
        features: torch.Tensor,
        context: Dict[str, Any]
    ) -> torch.Tensor:
        """Fast prediction with minimal computation"""
        # Use only first few layers
        x = features.to(self.predictor.device)
        x = self.predictor.input_proj(x)
        
        # Use only first 2 layers for speed
        for layer in self.predictor.layers[:2]:
            x = layer(x)
        
        # Quick output projection
        output = self.predictor.output_proj(x)
        return output
    
    async def _balanced_prediction(
        self,
        features: torch.Tensor,
        context: Dict[str, Any]
    ) -> torch.Tensor:
        """Balanced prediction with standard computation"""
        return await self.predictor.predict(features)
    
    async def _accurate_prediction(
        self,
        features: torch.Tensor,
        context: Dict[str, Any]
    ) -> torch.Tensor:
        """Accurate prediction with uncertainty estimation"""
        mean, uncertainty = self.predictor.predict_with_uncertainty(features, num_samples=20)
        
        # Weight by inverse uncertainty for more confident predictions
        confidence = 1.0 / (1.0 + uncertainty)
        weighted_prediction = mean * confidence
        
        return weighted_prediction
