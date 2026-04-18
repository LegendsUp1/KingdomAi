"""
Text Encoder for VL-JEPA
=========================

Encodes text inputs into continuous embeddings and decodes embeddings back to text.
Uses transformer architecture optimized for embedding prediction.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Union, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class TextEncoder(nn.Module):
    """
    Text encoder that processes text inputs into continuous embeddings.
    Supports both encoding (text -> embedding) and decoding (embedding -> text).
    """
    
    def __init__(
        self,
        vocab_size: int = 32000,
        max_length: int = 2048,
        embed_dim: int = 768,
        depth: int = 12,
        num_heads: int = 12,
        mlp_ratio: float = 4.0,
        dropout: float = 0.1,
        output_dim: int = 768,
        device: torch.device = torch.device('cpu')
    ):
        super().__init__()
        
        self.vocab_size = vocab_size
        self.max_length = max_length
        self.embed_dim = embed_dim
        self.output_dim = output_dim
        self.device = device
        
        # Token embedding
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        
        # Position embedding
        self.pos_embed = nn.Embedding(max_length, embed_dim)
        
        # Transformer encoder layers
        self.layers = nn.ModuleList([
            TransformerEncoderLayer(
                d_model=embed_dim,
                nhead=num_heads,
                dim_feedforward=int(embed_dim * mlp_ratio),
                dropout=dropout
            )
            for _ in range(depth)
        ])
        
        # Output projection
        self.norm = nn.LayerNorm(embed_dim)
        self.output_proj = nn.Linear(embed_dim, output_dim)
        
        # Decoder head for text generation
        # Add projection layer to handle dimension mismatch
        self.decoder_projection = nn.Linear(output_dim, embed_dim)
        self.decoder_head = nn.Linear(embed_dim, vocab_size)
        
        # Initialize weights
        self._init_weights()
        
        # Move to device
        self.to(device)
        
        # Simple tokenizer (can be replaced with proper tokenizer)
        self.tokenizer = SimpleTokenizer(vocab_size)
        
        logger.info(f"Text encoder initialized with {depth} layers, vocab size {vocab_size}")
    
    def _init_weights(self):
        """Initialize weights"""
        nn.init.normal_(self.token_embed.weight, std=0.02)
        nn.init.normal_(self.pos_embed.weight, std=0.02)
        nn.init.xavier_uniform_(self.output_proj.weight)
        nn.init.zeros_(self.output_proj.bias)
        nn.init.xavier_uniform_(self.decoder_projection.weight)
        nn.init.zeros_(self.decoder_projection.bias)
        nn.init.xavier_uniform_(self.decoder_head.weight)
        nn.init.zeros_(self.decoder_head.bias)
    
    async def encode(
        self,
        text_input: Union[str, List[str], torch.Tensor, Dict[str, Any]]
    ) -> torch.Tensor:
        """
        Encode text input to continuous embedding.
        
        Args:
            text_input: Text string, list of strings, token tensor, or dict
            
        Returns:
            Continuous embedding tensor
        """
        try:
            # Extract text
            if isinstance(text_input, dict):
                text = text_input.get('text') or text_input.get('prompt') or text_input.get('message')
                if text is None:
                    return torch.zeros(self.output_dim, device=self.device)
            elif isinstance(text_input, torch.Tensor):
                tokens = text_input
                text = None
            else:
                text = text_input
                tokens = None
            
            # Tokenize if needed
            if text is not None:
                if isinstance(text, list):
                    # Batch of texts
                    tokens_list = [self.tokenizer.encode(t) for t in text]
                    max_len = max(len(t) for t in tokens_list)
                    # Pad sequences
                    padded = []
                    for t in tokens_list:
                        if len(t) < max_len:
                            t = t + [0] * (max_len - len(t))
                        padded.append(t[:self.max_length])
                    tokens = torch.tensor(padded, device=self.device)
                else:
                    # Single text
                    token_ids = self.tokenizer.encode(text)[:self.max_length]
                    tokens = torch.tensor(token_ids, device=self.device).unsqueeze(0)
            
            # Move to device
            tokens = tokens.to(self.device)
            
            # Forward pass
            embedding = self.forward(tokens)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error encoding text input: {e}")
            return torch.zeros(self.output_dim, device=self.device)
    
    async def decode(
        self,
        embedding: torch.Tensor,
        context: Optional[Dict[str, Any]] = None,
        max_length: int = 100,
        temperature: float = 0.7
    ) -> str:
        """
        Decode continuous embedding back to text.
        
        Args:
            embedding: Continuous embedding tensor
            context: Optional context for guided decoding
            max_length: Maximum generation length
            temperature: Sampling temperature
            
        Returns:
            Decoded text string
        """
        try:
            # Ensure embedding is on device
            embedding = embedding.to(self.device)
            
            # If batch dimension missing, add it
            if len(embedding.shape) == 1:
                embedding = embedding.unsqueeze(0)
            
            # Project embedding to vocabulary
            # First project from output_dim to embed_dim, then to vocab
            projected = self.decoder_projection(embedding)
            logits = self.decoder_head(projected)
            
            # Apply temperature
            logits = logits / temperature
            
            # Sample tokens
            probs = F.softmax(logits, dim=-1)
            
            # Generate text autoregressively
            generated_tokens = []
            
            for _ in range(max_length):
                # Sample token
                if len(probs.shape) == 3:
                    # Take last position
                    token_probs = probs[0, -1, :]
                else:
                    token_probs = probs[0, :]
                
                token = torch.multinomial(token_probs, num_samples=1)
                generated_tokens.append(token.item())
                
                # Stop if EOS token
                if token.item() == self.tokenizer.eos_token_id:
                    break
                
                # Update embedding for next prediction (simplified)
                # In full implementation, this would use proper autoregressive generation
                noise = torch.randn_like(embedding) * 0.1
                embedding = embedding + noise
                projected = self.decoder_projection(embedding)
                logits = self.decoder_head(projected)
                logits = logits / temperature
                probs = F.softmax(logits, dim=-1)
            
            # Decode tokens to text
            text = self.tokenizer.decode(generated_tokens)
            
            return text
            
        except Exception as e:
            logger.error(f"Error decoding embedding: {e}")
            return f"[Decoding error: {str(e)}]"
    
    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        """Forward pass through text encoder"""
        B, L = tokens.shape
        
        # Token embeddings
        x = self.token_embed(tokens)
        
        # Position embeddings
        positions = torch.arange(L, device=self.device).unsqueeze(0).expand(B, -1)
        x = x + self.pos_embed(positions)
        
        # Apply transformer layers
        for layer in self.layers:
            x = layer(x)
        
        # Final normalization
        x = self.norm(x)
        
        # Pool over sequence (mean pooling)
        x = x.mean(dim=1)
        
        # Project to output dimension
        output = self.output_proj(x)
        
        return output
    
    def generate(
        self,
        prompt: str,
        max_length: int = 100,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> str:
        """
        Generate text from prompt using autoregressive generation.
        This is used when VL-JEPA needs to generate text responses.
        """
        # Tokenize prompt
        tokens = self.tokenizer.encode(prompt)
        tokens = torch.tensor(tokens, device=self.device).unsqueeze(0)
        
        generated = tokens.clone()
        
        with torch.no_grad():
            for _ in range(max_length):
                # Get embeddings
                x = self.token_embed(generated)
                positions = torch.arange(generated.size(1), device=self.device).unsqueeze(0)
                x = x + self.pos_embed(positions)
                
                # Apply transformer layers
                for layer in self.layers:
                    x = layer(x)
                
                x = self.norm(x)
                
                # Get logits for last position
                logits = self.decoder_head(self.output_proj(x[:, -1, :]))
                
                # Apply temperature
                logits = logits / temperature
                
                # Apply top-p sampling
                sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                
                # Remove tokens with cumulative probability above threshold
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = 0
                
                indices_to_remove = sorted_indices[sorted_indices_to_remove]
                logits[:, indices_to_remove] = float('-inf')
                
                # Sample
                probs = F.softmax(logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
                
                # Append to generated
                generated = torch.cat([generated, next_token], dim=1)
                
                # Stop if EOS
                if next_token.item() == self.tokenizer.eos_token_id:
                    break
        
        # Decode
        generated_text = self.tokenizer.decode(generated[0].tolist())
        return generated_text


class TransformerEncoderLayer(nn.Module):
    """Single transformer encoder layer"""
    
    def __init__(
        self,
        d_model: int,
        nhead: int,
        dim_feedforward: int = 2048,
        dropout: float = 0.1
    ):
        super().__init__()
        
        self.self_attn = nn.MultiheadAttention(
            d_model, nhead, dropout=dropout, batch_first=True
        )
        self.norm1 = nn.LayerNorm(d_model)
        
        self.ff = nn.Sequential(
            nn.Linear(d_model, dim_feedforward),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim_feedforward, d_model),
            nn.Dropout(dropout)
        )
        self.norm2 = nn.LayerNorm(d_model)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Self-attention
        x_norm = self.norm1(x)
        attn_out, _ = self.self_attn(x_norm, x_norm, x_norm)
        x = x + attn_out
        
        # Feed-forward
        x = x + self.ff(self.norm2(x))
        
        return x


class SimpleTokenizer:
    """Simple character-level tokenizer for demonstration"""
    
    def __init__(self, vocab_size: int):
        self.vocab_size = vocab_size
        self.eos_token_id = 0
        self.pad_token_id = 1
        self.unk_token_id = 2
        
        # Create simple char-to-id mapping
        self.char_to_id = {}
        self.id_to_char = {}
        
        # Special tokens
        self.char_to_id['<EOS>'] = 0
        self.char_to_id['<PAD>'] = 1
        self.char_to_id['<UNK>'] = 2
        
        # ASCII printable characters
        idx = 3
        for i in range(32, 127):  # Printable ASCII
            if idx < vocab_size:
                self.char_to_id[chr(i)] = idx
                self.id_to_char[idx] = chr(i)
                idx += 1
        
        self.id_to_char[0] = '<EOS>'
        self.id_to_char[1] = '<PAD>'
        self.id_to_char[2] = '<UNK>'
    
    def encode(self, text: str) -> List[int]:
        """Encode text to token ids"""
        tokens = []
        for char in text:
            if char in self.char_to_id:
                tokens.append(self.char_to_id[char])
            else:
                tokens.append(self.unk_token_id)
        return tokens
    
    def decode(self, token_ids: List[int]) -> str:
        """Decode token ids to text"""
        chars = []
        for token_id in token_ids:
            if token_id in self.id_to_char:
                char = self.id_to_char[token_id]
                if char not in ['<EOS>', '<PAD>', '<UNK>']:
                    chars.append(char)
            else:
                chars.append('?')
        return ''.join(chars)
