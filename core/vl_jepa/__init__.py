"""
VL-JEPA (Vision-Language Joint Embedding Predictive Architecture) Integration
==============================================================================

State-of-the-art architecture from Meta FAIR (December 2024) that predicts 
continuous embeddings instead of generating tokens, achieving better performance 
with 50% fewer parameters.

Key Features:
- Continuous embedding prediction in abstract representation space
- Selective decoding with 2.85x reduction in operations
- Native support for classification, retrieval, and VQA tasks
- Task-relevant semantic focusing with surface-level abstraction
"""

from .core import VLJEPACore
from .vision_encoder import VisionEncoder
from .text_encoder import TextEncoder
from .predictor_network import PredictorNetwork
from .embedding_space import EmbeddingSpace
from .integration import VLJEPAIntegration

__all__ = [
    'VLJEPACore',
    'VisionEncoder', 
    'TextEncoder',
    'PredictorNetwork',
    'EmbeddingSpace',
    'VLJEPAIntegration'
]

__version__ = '1.0.0'
