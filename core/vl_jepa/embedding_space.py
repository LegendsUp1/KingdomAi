"""
Embedding Space Manager for VL-JEPA
====================================

Manages the joint embedding space where vision and text representations
converge. Handles projection, normalization, and similarity computations.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import logging
from collections import deque

logger = logging.getLogger(__name__)


class EmbeddingSpace(nn.Module):
    """
    Manages the joint embedding space for VL-JEPA.
    Provides projection, retrieval, and learning capabilities.
    """
    
    def __init__(
        self,
        dim: int = 1024,
        temperature: float = 0.07,
        max_embeddings: int = 10000,
        device: torch.device = torch.device('cpu')
    ):
        super().__init__()
        
        self.dim = dim
        self.temperature = temperature
        self.max_embeddings = max_embeddings
        self.device = device
        
        # Projection layers for refinement
        self.refine_proj = nn.Sequential(
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.GELU(),
            nn.Linear(dim, dim)
        )
        
        # Memory bank for storing embeddings
        self.embedding_memory = deque(maxlen=max_embeddings)
        self.embedding_metadata = deque(maxlen=max_embeddings)
        
        # Learnable prototypes for common concepts
        self.num_prototypes = 256
        self.prototypes = nn.Parameter(torch.randn(self.num_prototypes, dim))
        
        # Statistics tracking
        self.stats = {
            'total_embeddings': 0,
            'retrieval_calls': 0,
            'pattern_updates': 0,
            'average_similarity': 0.0
        }
        
        # Initialize weights
        self._init_weights()
        
        # Move to device
        self.to(device)
        
        logger.info(f"Embedding space initialized with dimension {dim}")
    
    def _init_weights(self):
        """Initialize weights"""
        for module in self.refine_proj.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
        
        # Initialize prototypes
        nn.init.xavier_uniform_(self.prototypes)
    
    async def project(self, embedding: torch.Tensor) -> torch.Tensor:
        """
        Project embedding into the joint space with refinement.
        
        Args:
            embedding: Input embedding
            
        Returns:
            Refined embedding in joint space
        """
        try:
            # Ensure on device
            embedding = embedding.to(self.device)
            
            # Refine embedding
            refined = self.refine_proj(embedding)
            
            # L2 normalize for cosine similarity
            refined = F.normalize(refined, p=2, dim=-1)
            
            # Store in memory
            self._store_embedding(refined)
            
            return refined
            
        except Exception as e:
            logger.error(f"Error projecting embedding: {e}")
            return embedding
    
    def _store_embedding(self, embedding: torch.Tensor, metadata: Optional[Dict[str, Any]] = None):
        """Store embedding in memory bank"""
        # Detach to avoid memory issues
        embedding_cpu = embedding.detach().cpu()
        
        self.embedding_memory.append(embedding_cpu)
        self.embedding_metadata.append(metadata or {})
        
        self.stats['total_embeddings'] += 1
    
    async def retrieve_similar(
        self,
        query: torch.Tensor,
        k: int = 5,
        threshold: float = 0.7
    ) -> List[Tuple[torch.Tensor, Dict[str, Any], float]]:
        """
        Retrieve k most similar embeddings from memory.
        
        Args:
            query: Query embedding
            k: Number of results to return
            threshold: Similarity threshold
            
        Returns:
            List of (embedding, metadata, similarity) tuples
        """
        try:
            if not self.embedding_memory:
                return []
            
            # Ensure query is normalized
            query = F.normalize(query.to(self.device), p=2, dim=-1)
            
            # Stack all embeddings
            memory_stack = torch.stack(list(self.embedding_memory)).to(self.device)
            
            # Compute similarities
            similarities = torch.matmul(query, memory_stack.transpose(-2, -1))
            
            # Get top-k
            if len(similarities.shape) > 1:
                similarities = similarities.squeeze(0)
            
            top_k_values, top_k_indices = torch.topk(similarities, min(k, len(similarities)))
            
            # Filter by threshold and prepare results
            results = []
            for idx, sim in zip(top_k_indices, top_k_values):
                if sim.item() >= threshold:
                    results.append((
                        self.embedding_memory[idx],
                        self.embedding_metadata[idx],
                        sim.item()
                    ))
            
            self.stats['retrieval_calls'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error in retrieve_similar: {e}")
            return []
    
    async def update_with_patterns(self, patterns: List[Dict[str, Any]]):
        """
        Update embedding space with learned patterns.
        This refines the prototypes based on observed patterns.
        """
        try:
            if not patterns:
                return
            
            # Extract embeddings from patterns
            pattern_embeddings = []
            for pattern in patterns:
                if 'embedding' in pattern:
                    emb = pattern['embedding']
                    if isinstance(emb, torch.Tensor):
                        pattern_embeddings.append(emb)
            
            if not pattern_embeddings:
                return
            
            # Stack and move to device
            pattern_stack = torch.stack(pattern_embeddings).to(self.device)
            
            # Update prototypes using exponential moving average
            with torch.no_grad():
                # Find nearest prototype for each pattern
                similarities = torch.matmul(
                    F.normalize(pattern_stack, p=2, dim=-1),
                    F.normalize(self.prototypes, p=2, dim=-1).T
                )
                
                nearest_prototypes = torch.argmax(similarities, dim=1)
                
                # Update prototypes
                alpha = 0.1  # Learning rate
                for i, proto_idx in enumerate(nearest_prototypes):
                    self.prototypes[proto_idx] = (
                        (1 - alpha) * self.prototypes[proto_idx] +
                        alpha * pattern_stack[i]
                    )
            
            self.stats['pattern_updates'] += len(patterns)
            
        except Exception as e:
            logger.error(f"Error updating with patterns: {e}")
    
    def compute_similarity(
        self,
        emb1: torch.Tensor,
        emb2: torch.Tensor,
        metric: str = 'cosine'
    ) -> torch.Tensor:
        """
        Compute similarity between two embeddings.
        
        Args:
            emb1: First embedding
            emb2: Second embedding
            metric: Similarity metric ('cosine', 'euclidean', 'dot')
            
        Returns:
            Similarity score
        """
        emb1 = emb1.to(self.device)
        emb2 = emb2.to(self.device)
        
        if metric == 'cosine':
            emb1_norm = F.normalize(emb1, p=2, dim=-1)
            emb2_norm = F.normalize(emb2, p=2, dim=-1)
            similarity = torch.sum(emb1_norm * emb2_norm, dim=-1)
        elif metric == 'euclidean':
            similarity = -torch.norm(emb1 - emb2, p=2, dim=-1)
        elif metric == 'dot':
            similarity = torch.sum(emb1 * emb2, dim=-1)
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        return similarity
    
    def get_prototype_embedding(self, concept_id: int) -> torch.Tensor:
        """Get a learned prototype embedding for a concept"""
        if concept_id < 0 or concept_id >= self.num_prototypes:
            raise ValueError(f"Invalid concept_id: {concept_id}")
        
        return self.prototypes[concept_id]
    
    def find_nearest_prototype(self, embedding: torch.Tensor) -> Tuple[int, float]:
        """
        Find the nearest prototype to an embedding.
        
        Returns:
            Tuple of (prototype_id, similarity)
        """
        embedding = F.normalize(embedding.to(self.device), p=2, dim=-1)
        prototypes_norm = F.normalize(self.prototypes, p=2, dim=-1)
        
        similarities = torch.matmul(embedding, prototypes_norm.T)
        
        if len(similarities.shape) > 1:
            similarities = similarities.squeeze(0)
        
        max_sim, max_idx = torch.max(similarities, dim=0)
        
        return int(max_idx.item()), float(max_sim.item())
    
    def cluster_embeddings(self, embeddings: List[torch.Tensor], num_clusters: int = 10) -> List[int]:
        """
        Cluster embeddings using k-means in the embedding space.
        
        Args:
            embeddings: List of embeddings to cluster
            num_clusters: Number of clusters
            
        Returns:
            List of cluster assignments
        """
        if not embeddings:
            return []
        
        # Stack embeddings
        emb_stack = torch.stack(embeddings).to(self.device)
        
        # Simple k-means clustering
        centroids = emb_stack[torch.randperm(len(emb_stack))[:num_clusters]]
        
        for _ in range(10):  # Max iterations
            # Assign to nearest centroid
            distances = torch.cdist(emb_stack, centroids)
            assignments = torch.argmin(distances, dim=1)
            
            # Update centroids
            new_centroids = []
            for k in range(num_clusters):
                mask = assignments == k
                if mask.any():
                    new_centroids.append(emb_stack[mask].mean(dim=0))
                else:
                    new_centroids.append(centroids[k])
            
            centroids = torch.stack(new_centroids)
        
        return assignments.cpu().tolist()
    
    def interpolate(
        self,
        emb1: torch.Tensor,
        emb2: torch.Tensor,
        alpha: float = 0.5
    ) -> torch.Tensor:
        """
        Interpolate between two embeddings.
        
        Args:
            emb1: First embedding
            emb2: Second embedding
            alpha: Interpolation factor (0 = emb1, 1 = emb2)
            
        Returns:
            Interpolated embedding
        """
        emb1 = emb1.to(self.device)
        emb2 = emb2.to(self.device)
        
        # Linear interpolation
        interpolated = (1 - alpha) * emb1 + alpha * emb2
        
        # Renormalize
        interpolated = F.normalize(interpolated, p=2, dim=-1)
        
        return interpolated
    
    def get_stats(self) -> Dict[str, Any]:
        """Get embedding space statistics"""
        # Compute average similarity if we have embeddings
        if len(self.embedding_memory) > 1:
            memory_stack = torch.stack(list(self.embedding_memory)).to(self.device)
            memory_norm = F.normalize(memory_stack, p=2, dim=-1)
            
            # Compute pairwise similarities
            similarities = torch.matmul(memory_norm, memory_norm.T)
            
            # Mask diagonal (self-similarity)
            mask = ~torch.eye(len(memory_stack), dtype=torch.bool, device=self.device)
            similarities = similarities[mask]
            
            self.stats['average_similarity'] = similarities.mean().item()
        
        return {
            **self.stats,
            'memory_size': len(self.embedding_memory),
            'num_prototypes': self.num_prototypes
        }


class ContrastiveLoss(nn.Module):
    """
    Contrastive loss for training VL-JEPA embeddings.
    Based on InfoNCE loss.
    """
    
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature
    
    def forward(
        self,
        anchor: torch.Tensor,
        positive: torch.Tensor,
        negatives: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Compute contrastive loss.
        
        Args:
            anchor: Anchor embeddings (B, D)
            positive: Positive embeddings (B, D)
            negatives: Negative embeddings (B, N, D) or None for in-batch negatives
            
        Returns:
            Contrastive loss
        """
        # Normalize embeddings
        anchor = F.normalize(anchor, p=2, dim=-1)
        positive = F.normalize(positive, p=2, dim=-1)
        
        # Compute positive similarity
        pos_sim = torch.sum(anchor * positive, dim=-1) / self.temperature
        
        if negatives is None:
            # Use in-batch negatives
            batch_size = anchor.shape[0]
            
            # All pairwise similarities
            sim_matrix = torch.matmul(anchor, anchor.T) / self.temperature
            
            # Mask out diagonal (self-similarity)
            mask = torch.eye(batch_size, dtype=torch.bool, device=anchor.device)
            neg_sim = sim_matrix[~mask].view(batch_size, -1)
        else:
            # Use provided negatives
            negatives = F.normalize(negatives, p=2, dim=-1)
            neg_sim = torch.matmul(anchor.unsqueeze(1), negatives.transpose(-2, -1)).squeeze(1) / self.temperature
        
        # Compute InfoNCE loss
        logits = torch.cat([pos_sim.unsqueeze(1), neg_sim], dim=1)
        labels = torch.zeros(logits.shape[0], dtype=torch.long, device=logits.device)
        
        loss = F.cross_entropy(logits, labels)
        
        return loss
