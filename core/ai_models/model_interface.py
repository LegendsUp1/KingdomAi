#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI - Model Interface

This module defines the interface for interacting with AI models in the Kingdom AI system.
It provides a consistent API for different model backends.
"""

import logging
from typing import Dict, List, Optional, Any

# Set up logger
logger = logging.getLogger(__name__)

class ModelInterface:
    """Base interface for AI model interactions.
    
    This class defines the standard interface for communicating with
    AI models in the Kingdom AI system. It supports various model types
    including Ollama, GPT, and Claude models.
    """
    
    def __init__(self, model_name: str = "gemini-1.5-pro", config: Optional[Dict[str, Any]] = None):
        """Initialize the model interface.
        
        Args:
            model_name: Name of the model to use (default: gemini-1.5-pro)
            config: Additional configuration options
        """
        self.model_name = model_name
        self.config = config or {}
        self.is_connected = False
        self.model_info = {}
        
    def get_model_name(self) -> str:
        """Get the current model name.
        
        Returns:
            Current model name
        """
        return self.model_name
    
    def set_model_name(self, model_name: str) -> bool:
        """Set the model to use.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Success status
        """
        self.model_name = model_name
        return True
    
    async def connect(self) -> bool:
        """Connect to the model service.
        
        Returns:
            Success status
        """
        # Default implementation - override in subclasses
        self.is_connected = True
        return self.is_connected
    
    async def disconnect(self) -> bool:
        """Disconnect from the model service.
        
        Returns:
            Success status
        """
        # Default implementation - override in subclasses
        self.is_connected = False
        return not self.is_connected
    
    async def get_completion(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Get a model completion for the given prompt.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional parameters for the completion
            
        Returns:
            Response from the model
        """
        # Default implementation - override in subclasses
        logger.warning("Base model_interface.get_completion called - this should be overridden")
        return {
            "text": f"Base model interface called — subclass {self.__class__.__name__} should override generate()",
            "model": self.model_name,
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": 0,
            "total_tokens": len(prompt.split()),
            "finish_reason": "base_interface"
        }
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get a list of available models.
        
        Returns:
            List of model information dictionaries
        """
        # Default implementation - override in subclasses
        return [{
            "id": self.model_name,
            "name": self.model_name,
            "provider": "default",
            "context_window": 8192,
            "is_available": self.is_connected
        }]
    
    def get_model_info(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed information about a specific model.
        
        Args:
            model_id: Optional model ID (defaults to current model)
            
        Returns:
            Model information dictionary
        """
        model_id = model_id or self.model_name
        return {
            "id": model_id,
            "name": model_id,
            "provider": "default",
            "context_window": 8192,
            "is_available": self.is_connected
        }
