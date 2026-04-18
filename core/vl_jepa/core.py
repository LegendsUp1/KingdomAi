"""
VL-JEPA Core Implementation
===========================

Core VL-JEPA architecture that coordinates vision encoder, text encoder,
predictor network, and embedding space for continuous representation learning.
"""

import asyncio
import logging
import numpy as np
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class VLJEPAConfig:
    """Configuration for VL-JEPA model"""
    vision_dim: int = 768  # Vision encoder output dimension
    text_dim: int = 768    # Text encoder output dimension
    embed_dim: int = 1024  # Joint embedding dimension
    predictor_dim: int = 512  # Predictor network dimension
    num_predictor_layers: int = 6
    dropout: float = 0.1
    selective_decode_threshold: float = 0.8  # For 2.85x decoding reduction
    learning_window_size: int = 24  # Hours for learning context
    max_sequence_length: int = 2048
    temperature: float = 0.7
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


class VLJEPACore:
    """
    Core VL-JEPA implementation following Meta FAIR architecture.
    
    Instead of autoregressive token generation, predicts continuous embeddings
    in abstract representation space for improved efficiency and performance.
    """
    
    def __init__(self, config: Optional[VLJEPAConfig] = None, event_bus=None):
        """Initialize VL-JEPA core with configuration"""
        self.config = config or VLJEPAConfig()
        self.event_bus = event_bus
        self.device = torch.device(self.config.device)
        
        # Components will be initialized lazily
        self.vision_encoder = None
        self.text_encoder = None
        self.predictor_network = None
        self.embedding_space = None
        
        # Learning context buffers
        self.context_buffer: List[Dict[str, Any]] = []
        self.embedding_cache: Dict[str, torch.Tensor] = {}
        
        # Metrics tracking
        self.metrics = {
            'predictions_made': 0,
            'selective_decodes': 0,
            'cache_hits': 0,
            'learning_score': 0.0
        }
        
        logger.info(f"VL-JEPA Core initialized with device: {self.device}")
    
    async def initialize(self):
        """Async initialization of VL-JEPA components"""
        try:
            # Import component classes
            from .vision_encoder import VisionEncoder
            from .text_encoder import TextEncoder
            from .predictor_network import PredictorNetwork
            from .embedding_space import EmbeddingSpace
            
            # Initialize encoders
            self.vision_encoder = VisionEncoder(
                embed_dim=self.config.embed_dim,  # Use embed_dim for internal dimensions
                output_dim=self.config.embed_dim,  # Use embed_dim for output
                num_heads=16,  # 1024/16 = 64 (must be divisible)
                device=self.device
            )
            
            self.text_encoder = TextEncoder(
                embed_dim=self.config.embed_dim,  # Use embed_dim for internal dimensions
                output_dim=self.config.embed_dim,  # Use embed_dim for decoding compatibility
                num_heads=16,  # 1024/16 = 64 (must be divisible)
                max_length=self.config.max_sequence_length,
                device=self.device
            )
            
            # Initialize predictor network
            self.predictor_network = PredictorNetwork(
                input_dim=self.config.embed_dim * 2,  # Both encoders output embed_dim
                hidden_dim=self.config.predictor_dim,
                output_dim=self.config.embed_dim,
                num_layers=self.config.num_predictor_layers,
                dropout=self.config.dropout,
                device=self.device
            )
            
            # Initialize embedding space manager
            self.embedding_space = EmbeddingSpace(
                dim=self.config.embed_dim,
                device=self.device
            )
            
            # Subscribe to events if event bus available
            if self.event_bus:
                await self._setup_event_subscriptions()
            
            logger.info("VL-JEPA components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize VL-JEPA: {e}")
            return False
    
    async def _setup_event_subscriptions(self):
        """Set up event bus subscriptions for system integration"""
        if not self.event_bus:
            return
        
        # Subscribe to learning events
        self.event_bus.subscribe('learning.metrics', self._on_learning_metrics)
        self.event_bus.subscribe('learning.readiness', self._on_learning_readiness)
        
        # Subscribe to data events from all tabs
        self.event_bus.subscribe('trading.live_prices', self._on_trading_data)
        self.event_bus.subscribe('mining.hashrate', self._on_mining_data)
        self.event_bus.subscribe('blockchain.transaction', self._on_blockchain_data)
        # SOTA 2026 FIX: Do NOT subscribe to ai.request — ThothAI is the single handler.
        # Duplicate subscriptions caused 4-5x GPU contention on every user query.
        self.event_bus.subscribe('vision.frame', self._on_vision_frame)
        
        logger.info("VL-JEPA event subscriptions established")
    
    async def predict_embedding(
        self, 
        context: Dict[str, Any],
        use_selective_decode: bool = True
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Predict continuous embedding for given context.
        
        Args:
            context: Input context with vision/text/multimodal data
            use_selective_decode: Enable selective decoding for efficiency
            
        Returns:
            Tuple of (embedding tensor, metadata dict)
        """
        try:
            # Extract features from context
            features = await self._extract_features(context)
            
            # Check embedding cache
            cache_key = self._compute_cache_key(features)
            if cache_key in self.embedding_cache:
                self.metrics['cache_hits'] += 1
                cached_embedding = self.embedding_cache[cache_key]
                return cached_embedding, {'cached': True, 'confidence': 1.0}
            
            # Encode vision and text inputs
            vision_embedding = None
            text_embedding = None
            
            if 'vision' in features and self.vision_encoder:
                vision_embedding = await self.vision_encoder.encode(features['vision'])
            
            if 'text' in features and self.text_encoder:
                text_embedding = await self.text_encoder.encode(features['text'])
            
            # Combine embeddings
            combined = self._combine_embeddings(vision_embedding, text_embedding)
            
            # Predict with predictor network
            if self.predictor_network:
                predicted_embedding = await self.predictor_network.predict(combined)
            else:
                predicted_embedding = combined
            
            # Apply selective decoding
            confidence = 1.0
            if use_selective_decode:
                confidence = self._compute_decode_confidence(predicted_embedding)
                if confidence < self.config.selective_decode_threshold:
                    # Skip detailed decoding for low-confidence predictions
                    self.metrics['selective_decodes'] += 1
                    predicted_embedding = self._apply_fast_approximation(predicted_embedding)
            
            # Update embedding space
            if self.embedding_space:
                predicted_embedding = await self.embedding_space.project(predicted_embedding)
            
            # Cache the result
            self.embedding_cache[cache_key] = predicted_embedding
            
            # Update metrics
            self.metrics['predictions_made'] += 1
            
            metadata = {
                'cached': False,
                'confidence': confidence,
                'selective_decode': confidence < self.config.selective_decode_threshold,
                'dimension': predicted_embedding.shape[-1]
            }
            
            return predicted_embedding, metadata
            
        except Exception as e:
            logger.error(f"Error in predict_embedding: {e}")
            # Return zero embedding on error
            zero_embedding = torch.zeros(self.config.embed_dim, device=self.device)
            return zero_embedding, {'error': str(e)}
    
    async def decode_to_text(
        self, 
        embedding: torch.Tensor,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Decode continuous embedding back to text.
        Only invoked when text output is needed.
        """
        try:
            if self.text_encoder:
                text = await self.text_encoder.decode(embedding, context)
                return text
            else:
                return "Text decoder not initialized"
                
        except Exception as e:
            logger.error(f"Error decoding to text: {e}")
            return f"Decoding error: {str(e)}"
    
    async def learn_from_context(self, context: Dict[str, Any]):
        """
        Learn from system context to improve predictions.
        Integrates with learning orchestrator.
        """
        try:
            # Add to context buffer
            self.context_buffer.append(context)
            
            # Keep buffer size manageable
            max_buffer_size = 1000
            if len(self.context_buffer) > max_buffer_size:
                self.context_buffer = self.context_buffer[-max_buffer_size:]
            
            # Extract patterns for learning
            patterns = await self._extract_patterns(self.context_buffer)
            
            # Update embedding space with learned patterns
            if self.embedding_space:
                await self.embedding_space.update_with_patterns(patterns)
            
            # Publish learning event
            if self.event_bus:
                self.event_bus.publish('vl_jepa.learning_update', {
                    'patterns_learned': len(patterns),
                    'buffer_size': len(self.context_buffer),
                    'learning_score': self.metrics['learning_score']
                })
                
        except Exception as e:
            logger.error(f"Error in learn_from_context: {e}")
    
    def _combine_embeddings(
        self, 
        vision_emb: Optional[torch.Tensor], 
        text_emb: Optional[torch.Tensor]
    ) -> torch.Tensor:
        """Combine vision and text embeddings"""
        if vision_emb is not None and text_emb is not None:
            # Concatenate along feature dimension
            return torch.cat([vision_emb, text_emb], dim=-1)
        elif vision_emb is not None:
            # Pad to expected dimension (both encoders output embed_dim)
            padding = torch.zeros(
                (*vision_emb.shape[:-1], self.config.embed_dim),
                device=self.device
            )
            return torch.cat([vision_emb, padding], dim=-1)
        elif text_emb is not None:
            # Pad to expected dimension (both encoders output embed_dim)
            padding = torch.zeros(
                (*text_emb.shape[:-1], self.config.embed_dim),
                device=self.device
            )
            return torch.cat([padding, text_emb], dim=-1)
        else:
            # Return zero embedding (both encoders output embed_dim)
            return torch.zeros(
                self.config.embed_dim * 2,  # 2048 total
                device=self.device
            )
    
    def _compute_decode_confidence(self, embedding: torch.Tensor) -> float:
        """Compute confidence score for selective decoding"""
        try:
            # Compute embedding norm as confidence proxy
            norm = torch.norm(embedding).item()
            # Normalize to [0, 1] range
            confidence = torch.sigmoid(torch.tensor(norm / 10.0)).item()
            return confidence
        except:
            return 1.0
    
    def _apply_fast_approximation(self, embedding: torch.Tensor) -> torch.Tensor:
        """Apply fast approximation for selective decoding"""
        # Quantize to reduce precision for faster processing
        quantized = torch.round(embedding * 100) / 100
        return quantized
    
    def _compute_cache_key(self, features: Dict[str, Any]) -> str:
        """Compute cache key for features"""
        import hashlib
        import json
        
        # Create serializable version of features
        serializable = {}
        for key, value in features.items():
            if isinstance(value, torch.Tensor):
                serializable[key] = value.cpu().numpy().tolist()
            elif isinstance(value, np.ndarray):
                serializable[key] = value.tolist()
            else:
                serializable[key] = value
        
        # Hash the serialized features
        feature_str = json.dumps(serializable, sort_keys=True)
        return hashlib.md5(feature_str.encode()).hexdigest()
    
    async def _extract_features(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant features from context"""
        features = {}
        
        # Extract text features
        if 'text' in context:
            features['text'] = context['text']
        elif 'prompt' in context:
            features['text'] = context['prompt']
        elif 'message' in context:
            features['text'] = context['message']
        
        # Extract vision features
        if 'image' in context:
            features['vision'] = context['image']
        elif 'vision' in context:
            features['vision'] = context['vision']
        elif 'frame' in context:
            features['vision'] = context['frame']
        
        # Extract metadata features
        if 'metadata' in context:
            features['metadata'] = context['metadata']
        
        # Extract tab-specific features
        for tab in ['trading', 'mining', 'blockchain', 'wallet']:
            if tab in context:
                features[tab] = context[tab]
        
        return features
    
    async def _extract_patterns(self, buffer: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract learning patterns from context buffer"""
        patterns = []
        
        # Group by context type
        grouped = {}
        for ctx in buffer:
            ctx_type = ctx.get('type', 'unknown')
            if ctx_type not in grouped:
                grouped[ctx_type] = []
            grouped[ctx_type].append(ctx)
        
        # Extract patterns per type
        for ctx_type, contexts in grouped.items():
            if len(contexts) >= 2:
                # Find recurring patterns
                pattern = {
                    'type': ctx_type,
                    'frequency': len(contexts),
                    'features': self._find_common_features(contexts)
                }
                patterns.append(pattern)
        
        return patterns
    
    def _find_common_features(self, contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Find common features across contexts"""
        if not contexts:
            return {}
        
        # Start with first context's keys
        common = set(contexts[0].keys())
        
        # Find intersection with other contexts
        for ctx in contexts[1:]:
            common = common.intersection(set(ctx.keys()))
        
        # Build common features dict
        features = {}
        for key in common:
            # Check if values are consistent
            values = [ctx[key] for ctx in contexts if key in ctx]
            if len(set(map(type, values))) == 1:  # Same type
                features[key] = values[0]  # Take first value as representative
        
        return features
    
    # Event handlers
    async def _on_learning_metrics(self, data: Dict[str, Any]):
        """Handle learning metrics from orchestrator"""
        self.metrics['learning_score'] = data.get('learning_score', 0.0)
    
    async def _on_learning_readiness(self, data: Dict[str, Any]):
        """Handle learning readiness updates"""
        state = data.get('state', 'WARMUP')
        if state == 'READY':
            # Clear cache to use fresh learnings
            self.embedding_cache.clear()
    
    async def _on_trading_data(self, data: Dict[str, Any]):
        """Learn from trading data"""
        await self.learn_from_context({'type': 'trading', **data})
    
    async def _on_mining_data(self, data: Dict[str, Any]):
        """Learn from mining data"""
        await self.learn_from_context({'type': 'mining', **data})
    
    async def _on_blockchain_data(self, data: Dict[str, Any]):
        """Learn from blockchain data"""
        await self.learn_from_context({'type': 'blockchain', **data})
    
    async def _on_ai_request(self, data: Dict[str, Any]):
        """Handle AI requests with VL-JEPA"""
        try:
            if not isinstance(data, dict):
                return
            request_type = data.get('type', 'general')
            context = data.get('context', {})

            self.metrics['requests_processed'] = self.metrics.get('requests_processed', 0) + 1

            await self.learn_from_context({'type': request_type, **context})

            if self.event_bus:
                self.event_bus.publish("vl_jepa.request.processed", {
                    "request_type": request_type,
                    "metrics": self.get_metrics()
                })

            logger.debug("VL-JEPA processed AI request: type=%s", request_type)
        except Exception as e:
            logger.error("Error handling AI request: %s", e)
    
    async def _on_vision_frame(self, data: Dict[str, Any]):
        """Process vision frames"""
        await self.learn_from_context({'type': 'vision', **data})
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current VL-JEPA metrics"""
        return {
            **self.metrics,
            'cache_size': len(self.embedding_cache),
            'context_buffer_size': len(self.context_buffer),
            'device': str(self.device)
        }
