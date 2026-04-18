"""
ThothAI connector module for Kingdom AI.
Provides integration with Ollama and local LLM services.
"""
import logging
import aiohttp
import asyncio
import json
import os
from typing import Dict, Any, List, Optional, Union

# Import base component structure
from base_component import BaseComponent

logger = logging.getLogger(__name__)

class ThothAI(BaseComponent):
    """
    ThothAI connector for integrating with local Ollama and other LLM services.
    Provides AI inference capabilities for Kingdom AI.
    """
    
    def __init__(self, event_bus=None, base_url="http://localhost:11434"):
        # Initialize BaseComponent 
        super().__init__(monitor=None)
        # Store the event bus
        self.event_bus = event_bus
        # Create logger
        self.logger = logging.getLogger("ThothAI")
        # Initialize other attributes
        self.base_url = base_url
        self.session = None
        self._models = {}
        self._active_model = None
        
    async def initialize(self) -> bool:
        """Initialize the ThothAI connector"""
        self.logger.info("Initializing ThothAI connector")
        
        try:
            # Create aiohttp session
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Test connection to Ollama
            await self._test_connection()
            
            # Subscribe to events
            if self.event_bus:
                self.event_bus.subscribe("thoth.query", self._handle_query)
                self.event_bus.subscribe("thoth.list_models", self._handle_list_models)
                self.event_bus.subscribe("thoth.change_model", self._handle_change_model)
            
            # List available models
            await self._refresh_models()
            
            self._initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize ThothAI: {e}")
            return False
            
    async def shutdown(self) -> bool:
        """Shutdown the ThothAI connector"""
        try:
            if self.session:
                await self.session.close()
                self.session = None
            
            self.logger.info("ThothAI connector shut down successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error shutting down ThothAI connector: {e}")
            return False
            
    async def _test_connection(self) -> bool:
        """Test connection to Ollama service"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    return True
                self.logger.warning(f"Ollama returned status code: {response.status}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to Ollama: {e}")
            return False
            
    async def _refresh_models(self) -> None:
        """Refresh the list of available models"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    if "models" in data:
                        for model in data["models"]:
                            name = model.get("name", "")
                            if name:
                                self._models[name] = model
                        self.logger.info(f"Loaded {len(self._models)} models from Ollama")
                    else:
                        self.logger.warning("No models found in Ollama response")
                else:
                    self.logger.warning(f"Failed to get models: {response.status}")
        except Exception as e:
            self.logger.error(f"Error refreshing models: {e}")
            
    async def query(self, prompt: str, model: str = "llama3", system_prompt: str = None, 
                   temperature: float = 0.7, max_tokens: int = 1000) -> Dict[str, Any]:
        """
        Send a query to the language model
        
        Args:
            prompt: User query text
            model: Model name to use
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Dictionary with response text and metadata
        """
        if not self._initialized:
            self.logger.error("ThothAI not initialized")
            return {"error": "ThothAI not initialized"}
            
        try:
            # Check if model exists
            if model not in self._models:
                await self._refresh_models()
                if model not in self._models:
                    return {
                        "success": False,
                        "error": f"Model {model} not found"
                    }
            
            # Prepare payload
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            if system_prompt:
                payload["system"] = system_prompt
                
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            async with self.session.post(f"{self.base_url}/api/generate", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "response": result.get("response", ""),
                        "model": model,
                        "total_tokens": result.get("total_tokens", 0),
                        "prompt_tokens": result.get("prompt_tokens", 0),
                        "completion_tokens": result.get("completion_tokens", 0)
                    }
                else:
                    error = await response.text()
                    self.logger.error(f"Query failed: {response.status} - {error}")
                    return {
                        "success": False,
                        "error": f"Query failed with status {response.status}"
                    }
        except Exception as e:
            self.logger.error(f"Error in query: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def _handle_query(self, data: Dict[str, Any]) -> None:
        """Handle thoth.query event from event bus"""
        if not data:
            return
            
        prompt = data.get("prompt", "")
        if not prompt:
            return
            
        model = data.get("model", "llama3")
        system_prompt = data.get("system_prompt")
        temperature = data.get("temperature", 0.7)
        max_tokens = data.get("max_tokens", 1000)
        callback_event = data.get("callback_event", "thoth.response")
        
        response = await self.query(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Publish response to event bus
        if self.event_bus:
            self.event_bus.publish(callback_event, {
                "response": response,
                "original_query": data
            })
            
    async def _handle_list_models(self, data: Dict[str, Any] = None) -> None:
        """Handle thoth.list_models event from event bus"""
        await self._refresh_models()
        
        callback_event = "thoth.models_list"
        if data and "callback_event" in data:
            callback_event = data["callback_event"]
            
        if self.event_bus:
            self.event_bus.publish(callback_event, list(self._models.keys()))
            
    async def _handle_change_model(self, data: Dict[str, Any]) -> None:
        """Handle thoth.change_model event from event bus"""
        if not data or "model" not in data:
            return
            
        model_name = data["model"]
        if model_name not in self._models:
            # Try to refresh models to see if it's available
            await self._refresh_models()
            
            if model_name not in self._models:
                self.logger.error(f"Model {model_name} not available")
                if self.event_bus:
                    self.event_bus.publish("thoth.model_change_failed", {
                        "error": f"Model {model_name} not available",
                        "available_models": list(self._models.keys())
                    })
                return
        
        # Publish success event
        if self.event_bus:
            self.event_bus.publish("thoth.model_changed", {
                "model": model_name
            })
