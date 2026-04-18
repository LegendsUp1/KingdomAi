"""
Thoth AI Handlers Module

This module contains all AI-related handler methods and utility functions 
for the MCPConnector class that handles Multi-Model AI interactions.
"""

import asyncio
import logging
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

class AIHandlers:
    """AI handler methods to be integrated with MCPConnector class.
    
    This is a mixin class - attributes are provided by the host class (MCPConnector).
    """
    
    # Type hints for attributes provided by host class
    logger: logging.Logger
    event_bus: Any
    available_models: List[str]
    
    # Methods provided by host class
    async def discover_available_models(self, force_refresh: bool = False) -> List[str]: ...
    async def generate_completion(self, model: str, prompt: str) -> str: ...
    
    async def _handle_model_discovery(self, data):
        """Handle requests to discover available AI models.
        
        Args:
            data: Event data with discovery parameters
        """
        try:
            if not isinstance(data, dict):
                data = {}
                
            request_id = data.get('request_id', str(uuid.uuid4()))
            force_refresh = data.get('force_refresh', False)
            
            self.logger.info(f"Handling model discovery request (force_refresh={force_refresh})")
            
            # Discover available models
            try:
                models = await self.discover_available_models(force_refresh=force_refresh)
                
                # Publish results
                if self.event_bus:
                    await self.event_bus.publish("ai.model.discovery.response", {
                        "success": True,
                        "models": models,
                        "count": len(models),
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
                    
            except Exception as e:
                self.logger.error(f"Error discovering models: {str(e)}")
                
                # Publish error
                if self.event_bus:
                    await self.event_bus.publish("ai.model.discovery.response", {
                        "success": False,
                        "error": str(e),
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
                
        except Exception as e:
            self.logger.error(f"Error handling model discovery: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            # Try to publish error response
            if hasattr(self, 'event_bus') and self.event_bus:
                error_data = {
                    "success": False,
                    "error": str(e),
                    "request_id": "unknown"
                }
                
                # Safe access to data dictionary if it exists
                if isinstance(data, dict):
                    error_data["request_id"] = data.get("request_id", "unknown")
                
                await self.event_bus.publish("ai.model.discovery.response", error_data)

    async def _handle_capability_query(self, data):
        """Handle queries about AI model capabilities.
        
        Args:
            data: Event data with model and capability parameters
        """
        try:
            if not isinstance(data, dict):
                self.logger.error("Invalid capability query data: not a dictionary")
                return
                
            model_name = data.get('model')
            capability = data.get('capability')
            request_id = data.get('request_id', str(uuid.uuid4()))
            
            self.logger.info(f"Querying capabilities for model: {model_name}, capability: {capability}")
            
            # Default capability map (in a real implementation, this would be dynamically determined)
            capability_map = {
                "mistral-nemo:latest": {
                    "chat": True,
                    "code": False,
                    "analysis": True,
                    "embedding": False,
                    "vision": False
                },
                "mistral": {
                    "chat": True,
                    "code": True,
                    "analysis": True, 
                    "embedding": True,
                    "vision": False
                },
                "codellama": {
                    "chat": True,
                    "code": True, 
                    "analysis": False,
                    "embedding": False,
                    "vision": False
                },
                "phi": {
                    "chat": True,
                    "code": True,
                    "analysis": False,
                    "embedding": False, 
                    "vision": False
                },
                "gemma": {
                    "chat": True,
                    "code": False,
                    "analysis": True,
                    "embedding": False,
                    "vision": False
                }
            }
            
            # Get capability information
            result = {}
            if model_name:
                # For specific model
                if model_name in capability_map:
                    if capability:
                        # Specific capability for specific model
                        result = {
                            "model": model_name,
                            "capability": capability,
                            "supported": capability_map[model_name].get(capability, False)
                        }
                    else:
                        # All capabilities for specific model
                        result = {
                            "model": model_name,
                            "capabilities": capability_map.get(model_name, {})
                        }
                else:
                    # Model not found
                    if self.event_bus:
                        await self.event_bus.publish("ai.capability.query.response", {
                            "success": False,
                            "error": f"Model '{model_name}' not found",
                            "request_id": request_id,
                            "timestamp": datetime.now().isoformat()
                        })
                    return
            else:
                # For all models
                if capability:
                    # Specific capability across all models
                    result = {
                        "capability": capability,
                        "supported_models": [
                            model for model, caps in capability_map.items() 
                            if caps.get(capability, False)
                        ]
                    }
                else:
                    # All capabilities for all models
                    result = {
                        "capabilities": capability_map
                    }
            
            # Publish capability information
            if self.event_bus:
                await self.event_bus.publish("ai.capability.query.response", {
                    "success": True,
                    "result": result,
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error handling capability query: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            # Publish error response
            if self.event_bus:
                error_data = {
                    "success": False,
                    "error": str(e),
                    "request_id": "unknown"
                }
                
                # Safe access to data dictionary if it exists
                if isinstance(data, dict):
                    error_data["request_id"] = data.get("request_id", "unknown")
                
                await self.event_bus.publish("ai.capability.query.response", error_data)

    async def _handle_multi_model_consultation(self, data):
        """Handle multi-model consultation request.
        
        Args:
            data: Event data with consultation parameters
        """
        try:
            if not isinstance(data, dict):
                self.logger.error("Invalid multi-model consultation data: not a dictionary")
                return
                
            request_id = data.get('request_id', str(uuid.uuid4()))
            query = data.get('query')
            models = data.get('models', [])
            timeout = data.get('timeout', 30.0)
            
            if not query:
                self.logger.error("Empty query for multi-model consultation")
                if self.event_bus:
                    await self.event_bus.publish("ai.consultation.multi.response", {
                        "success": False,
                        "error": "Empty query",
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
                return
                
            # Use default models if none specified - all Ollama models (cloud + local)
            if not models or not isinstance(models, list) or len(models) == 0:
                if hasattr(self, 'available_models') and isinstance(self.available_models, list) and len(self.available_models) > 0:
                    models = self.available_models[:5]  # Use top 5 available models
                else:
                    # Default: cloud models first, then local fallbacks
                    models = [
                        "deepseek-v3.1:671b-cloud", "qwen3-coder:480b-cloud",
                        "mistral-nemo:latest", "cogito:latest", "phi4-mini:latest"
                    ]
            
            self.logger.info(f"Starting multi-model consultation with {len(models)} models: {', '.join(models)}")
            
            # Track start time for stats
            start_time = datetime.now()
            
            # Create tasks for each model response
            tasks = []
            for model in models:
                tasks.append(self.generate_completion(model, query))
                
            # Gather responses with timeout
            responses = []
            try:
                # Wait for all responses with timeout
                gathered = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process responses
                for i, result in enumerate(gathered):
                    if isinstance(result, Exception):
                        self.logger.warning(f"Error from model {models[i]}: {str(result)}")
                        responses.append({
                            "model": models[i],
                            "success": False,
                            "error": str(result)
                        })
                    else:
                        responses.append({
                            "model": models[i],
                            "success": True,
                            "response": result
                        })
                        
            except asyncio.TimeoutError:
                self.logger.warning(f"Multi-model consultation timed out after {timeout} seconds")
                
            # Calculate stats
            end_time = datetime.now()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            success_count = sum(1 for r in responses if r.get("success", False))
            
            # Publish consultation results
            if self.event_bus:
                await self.event_bus.publish("ai.consultation.multi.response", {
                    "success": len(responses) > 0,
                    "query": query,
                    "responses": responses,
                    "stats": {
                        "model_count": len(models),
                        "response_count": len(responses),
                        "success_count": success_count,
                        "duration_ms": duration_ms
                    },
                    "request_id": request_id,
                    "timestamp": end_time.isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error handling multi-model consultation: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            # Publish error response
            if self.event_bus:
                error_data = {
                    "success": False,
                    "error": str(e),
                    "request_id": "unknown"
                }
                
                # Safe access to data dictionary if it exists
                if isinstance(data, dict):
                    error_data["request_id"] = data.get("request_id", "unknown")
                
                await self.event_bus.publish("ai.consultation.multi.response", error_data)
