#!/usr/bin/env python3
"""
Kingdom AI - ThothAI Extensions

This module extends the ThothAI component with model coordination capabilities.
It provides enhanced functionality for the core AI system.

Author: Kingdom AI Development Team
Date: 2025-04-21
"""

import time
import logging
import asyncio
import traceback

class ThothAIExtensions:
    """
    Extensions for ThothAI to integrate with model coordination.
    Enhances the core AI component with advanced features.
    """
    
    def __init__(self, thoth_instance=None, event_bus=None):
        """Initialize ThothAI extensions."""
        self.name = "thoth_extensions"
        self.thoth = thoth_instance
        self.event_bus = event_bus
        self.logger = logging.getLogger("KingdomAI.ThothExtensions")
        self.logger.info("ThothAI Extensions initializing")
        
        # Initialization flag
        self.initialized = False
        
        # Model coordination components
        self.model_coordinator = None
        self.model_synchronizer = None
        self.model_cache = None
        
        # Performance tracking
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.cache_hits = 0
        
    def initialize(self):
        """Initialize ThothAI extensions."""
        if self.initialized:
            self.logger.info("ThothAI extensions already initialized")
            return True
            
        if not self.thoth:
            self.logger.error("Cannot initialize extensions: ThothAI instance not provided")
            return False
            
        self.logger.info("Initializing ThothAI extensions")
        
        try:
            # Import model coordination components
            try:
                from ai.model_coordinator import get_model_coordinator
                self.model_coordinator = get_model_coordinator(self.event_bus)
                self.logger.info("Model coordinator imported successfully")
            except ImportError:
                self.logger.warning("Model coordinator not available")
                
            try:
                from ai.model_sync import get_model_synchronizer
                self.model_synchronizer = get_model_synchronizer(self.event_bus)
                self.logger.info("Model synchronizer imported successfully")
            except ImportError:
                self.logger.warning("Model synchronizer not available")
                
            try:
                from ai.model_cache import get_model_cache
                self.model_cache = get_model_cache(self.event_bus)
                self.logger.info("Model cache imported successfully")
            except ImportError:
                self.logger.warning("Model cache not available")
            
            # Register with model coordinator if available
            if self.model_coordinator:
                self.model_coordinator.register_model(
                    "thoth_extended", 
                    self.__class__.__module__ + "." + self.__class__.__name__,
                    {"primary": True}
                )
            
            # Register with model synchronizer if available
            if self.model_synchronizer:
                if hasattr(self.model_synchronizer, 'register_model'):
                    self.model_synchronizer.register_model("thoth_extended")
            
            # Extend ThothAI with additional methods
            self._extend_thoth_instance()
            
            # Subscribe to events
            # CRITICAL FIX: Do NOT subscribe to ai.request here - thoth.py handles it
            # This was causing duplicate processing and double responses
            if self.event_bus and hasattr(self.event_bus, 'subscribe'):
                # Only subscribe to ai.response for monitoring/logging
                self.event_bus.subscribe("ai.response", self._handle_ai_response)
                
                # Publish initialization event
                if hasattr(self.event_bus, 'publish'):
                    self.event_bus.publish("component.status", {
                        "component": self.name,
                        "status": "initialized",
                        "timestamp": time.time()
                    })
            
            # Mark as initialized
            self.initialized = True
            
            self.logger.info("ThothAI extensions initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing ThothAI extensions: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            # Publish error event
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                self.event_bus.publish("component.error", {
                    "component": self.name,
                    "error": str(e),
                    "timestamp": time.time()
                })
                
            return False
    
    def _extend_thoth_instance(self):
        """Extend the ThothAI instance with additional methods."""
        # Store original methods for use in extended versions
        if not hasattr(self.thoth, '_original_generate'):
            self.thoth._original_generate = self.thoth.generate
            
        if not hasattr(self.thoth, '_original_analyze'):
            self.thoth._original_analyze = self.thoth.analyze
            
        # Replace methods with extended versions
        self.thoth.generate = self._extended_generate
        self.thoth.analyze = self._extended_analyze
        
        # Add new methods
        self.thoth.process_coordinated_request = self.process_coordinated_request
        
        self.logger.info("ThothAI instance extended with additional methods")
    
    async def _extended_generate(self, prompt, **kwargs):
        """Extended version of ThothAI generate method."""
        self.request_count += 1
        
        # Check cache if available
        if self.model_cache:
            cached_response = await self.model_cache.get(
                "thoth", 
                "generate", 
                {"prompt": prompt, "params": kwargs}
            )
            
            if cached_response:
                self.cache_hits += 1
                self.success_count += 1
                self.logger.info("Using cached generate response")
                return cached_response
        
        # Create request context if synchronizer available
        context_id = None
        if self.model_synchronizer:
            request_id = kwargs.get("request_id", str(time.time()))
            context_id = await self.model_synchronizer.create_request_context(
                request_id,
                {
                    "type": "generate",
                    "prompt": prompt,
                    "params": kwargs
                }
            )
        
        try:
            # Call original method
            if asyncio.iscoroutinefunction(self.thoth._original_generate):
                response = await self.thoth._original_generate(prompt, **kwargs)
            else:
                response = self.thoth._original_generate(prompt, **kwargs)
                
            # Store in cache if available
            if response and self.model_cache:
                await self.model_cache.store(
                    "thoth", 
                    "generate", 
                    {"prompt": prompt, "params": kwargs},
                    response
                )
            
            # Update context if available
            if context_id and self.model_synchronizer:
                await self.model_synchronizer.update_request_context(
                    context_id,
                    {
                        "responses": {
                            "thoth": {
                                "timestamp": time.time(),
                                "response": response
                            }
                        },
                        "status": "completed" if response else "failed"
                    }
                )
                
                # Close context
                await self.model_synchronizer.close_request_context(context_id)
            
            # Update metrics
            if response:
                self.success_count += 1
            else:
                self.failure_count += 1
                
            return response
            
        except Exception as e:
            self.logger.error(f"Error in extended generate: {str(e)}")
            self.failure_count += 1
            
            # Update context with error if available
            if context_id and self.model_synchronizer:
                await self.model_synchronizer.update_request_context(
                    context_id,
                    {
                        "status": "error",
                        "error": str(e)
                    }
                )
                
                # Close context
                await self.model_synchronizer.close_request_context(context_id)
            
            # Re-raise exception
            raise
    
    async def _extended_analyze(self, data, **kwargs):
        """Extended version of ThothAI analyze method."""
        self.request_count += 1
        
        # Check cache if available
        if self.model_cache:
            cached_response = await self.model_cache.get(
                "thoth", 
                "analyze", 
                {"data": data, "params": kwargs}
            )
            
            if cached_response:
                self.cache_hits += 1
                self.success_count += 1
                self.logger.info("Using cached analyze response")
                return cached_response
        
        # Create request context if synchronizer available
        context_id = None
        if self.model_synchronizer:
            request_id = kwargs.get("request_id", str(time.time()))
            context_id = await self.model_synchronizer.create_request_context(
                request_id,
                {
                    "type": "analyze",
                    "data": data,
                    "params": kwargs
                }
            )
        
        try:
            # Call original method
            if asyncio.iscoroutinefunction(self.thoth._original_analyze):
                response = await self.thoth._original_analyze(data, **kwargs)
            else:
                response = self.thoth._original_analyze(data, **kwargs)
                
            # Store in cache if available
            if response and self.model_cache:
                await self.model_cache.store(
                    "thoth", 
                    "analyze", 
                    {"data": data, "params": kwargs},
                    response
                )
            
            # Update context if available
            if context_id and self.model_synchronizer:
                await self.model_synchronizer.update_request_context(
                    context_id,
                    {
                        "responses": {
                            "thoth": {
                                "timestamp": time.time(),
                                "response": response
                            }
                        },
                        "status": "completed" if response else "failed"
                    }
                )
                
                # Close context
                await self.model_synchronizer.close_request_context(context_id)
            
            # Update metrics
            if response:
                self.success_count += 1
            else:
                self.failure_count += 1
                
            return response
            
        except Exception as e:
            self.logger.error(f"Error in extended analyze: {str(e)}")
            self.failure_count += 1
            
            # Update context with error if available
            if context_id and self.model_synchronizer:
                await self.model_synchronizer.update_request_context(
                    context_id,
                    {
                        "status": "error",
                        "error": str(e)
                    }
                )
                
                # Close context
                await self.model_synchronizer.close_request_context(context_id)
            
            # Re-raise exception
            raise
    
    async def process_coordinated_request(self, request_type, request_data, models=None):
        """
        Process a request using coordinated models.
        
        Args:
            request_type: Type of request
            request_data: Request data
            models: Optional list of models to use
            
        Returns:
            Processed response
        """
        self.request_count += 1
        
        # If model coordinator is not available, fall back to ThothAI
        if not self.model_coordinator:
            self.logger.warning("Model coordinator not available, falling back to ThothAI")
            
            if request_type == "generate" and isinstance(request_data, dict) and "prompt" in request_data:
                return await self._extended_generate(
                    request_data["prompt"], 
                    **{k: v for k, v in request_data.items() if k != "prompt"}
                )
            elif request_type == "analyze":
                return await self._extended_analyze(request_data)
            else:
                self.logger.error(f"Unsupported request type: {request_type}")
                return None
        
        # Use model coordinator
        try:
            # If specific models requested, try them in order
            if models:
                for model_id in models:
                    response = await self.model_coordinator.process_request(
                        request_type, 
                        request_data,
                        model_id
                    )
                    
                    if response:
                        self.success_count += 1
                        return response
                        
                # All specified models failed
                self.failure_count += 1
                return None
            else:
                # Use model coordinator's fallback sequence
                response = await self.model_coordinator.process_request(
                    request_type,
                    request_data
                )
                
                if response:
                    self.success_count += 1
                else:
                    self.failure_count += 1
                    
                return response
                
        except Exception as e:
            self.logger.error(f"Error in coordinated request: {str(e)}")
            self.logger.error(traceback.format_exc())
            self.failure_count += 1
            
            # Fallback to ThothAI in case of error
            try:
                self.logger.info("Falling back to ThothAI after coordinator error")
                
                if request_type == "generate" and isinstance(request_data, dict) and "prompt" in request_data:
                    return await self._extended_generate(
                        request_data["prompt"], 
                        **{k: v for k, v in request_data.items() if k != "prompt"}
                    )
                elif request_type == "analyze":
                    return await self._extended_analyze(request_data)
                else:
                    self.logger.error(f"Unsupported request type: {request_type}")
                    return None
                    
            except Exception as fallback_error:
                self.logger.error(f"Fallback to ThothAI also failed: {str(fallback_error)}")
                return None
    
    def _handle_ai_request(self, data):
        """Handle AI request events."""
        if not isinstance(data, dict):
            return
            
        # If this is a coordinated request, handle it
        if data.get("coordinated", False):
            request_type = data.get("type")
            request_data = data.get("data")
            models = data.get("models")
            request_id = data.get("request_id")
            
            if not request_type or not request_data:
                self.logger.warning("Invalid coordinated request: missing type or data")
                return
                
            # Process request asynchronously
            async def process():
                response = await self.process_coordinated_request(
                    request_type,
                    request_data,
                    models
                )
                
                # Publish response event
                if self.event_bus and hasattr(self.event_bus, 'publish'):
                    self.event_bus.publish("ai.coordinated.response", {
                        "request_id": request_id,
                        "type": request_type,
                        "response": response,
                        "status": "success" if response is not None else "failed",
                        "timestamp": time.time()
                    })
            
            if hasattr(asyncio, 'create_task'):
                asyncio.create_task(process())
    
    def _handle_ai_response(self, data):
        """Handle AI response events."""
        try:
            if not isinstance(data, dict):
                return
            model = data.get("model", "unknown")
            status = data.get("status", "unknown")
            latency = data.get("latency_ms", 0)

            self.request_count += 1
            if status == "success":
                self.success_count += 1
            elif status in ("error", "failed"):
                self.failure_count += 1

            if data.get("from_cache"):
                self.cache_hits += 1

            self.logger.debug(
                "AI response: model=%s, status=%s, latency=%dms (total=%d, success=%d)",
                model, status, latency, self.request_count, self.success_count
            )
        except Exception as e:
            self.logger.error("Error handling AI response: %s", e)
    
    def get_metrics(self):
        """Get performance metrics."""
        success_rate = 0
        cache_hit_rate = 0
        
        if self.request_count > 0:
            success_rate = self.success_count / self.request_count
            
        if self.success_count > 0:
            cache_hit_rate = self.cache_hits / self.success_count
            
        return {
            "request_count": self.request_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "cache_hits": self.cache_hits,
            "success_rate": success_rate,
            "cache_hit_rate": cache_hit_rate
        }
    
    def shutdown(self):
        """Shut down ThothAI extensions."""
        self.logger.info("Shutting down ThothAI extensions")
        
        # Restore original methods
        if hasattr(self.thoth, '_original_generate'):
            self.thoth.generate = self.thoth._original_generate
            
        if hasattr(self.thoth, '_original_analyze'):
            self.thoth.analyze = self.thoth._original_analyze
            
        # Remove added methods
        if hasattr(self.thoth, 'process_coordinated_request'):
            delattr(self.thoth, 'process_coordinated_request')
            
        # Unregister from model coordinator
        if self.model_coordinator:
            self.model_coordinator.unregister_model("thoth_extended")
            
        # Unregister from model synchronizer
        if self.model_synchronizer:
            if hasattr(self.model_synchronizer, 'unregister_model'):
                self.model_synchronizer.unregister_model("thoth_extended")
                
        self.logger.info("ThothAI extensions shut down successfully")
        
        # Publish shutdown event
        if self.event_bus and hasattr(self.event_bus, 'publish'):
            self.event_bus.publish("component.status", {
                "component": self.name,
                "status": "shutdown",
                "timestamp": time.time()
            })

# Factory function to create ThothAI extensions
def create_thoth_extensions(thoth_instance, event_bus=None):
    """Create a ThothAI extensions instance."""
    extensions = ThothAIExtensions(thoth_instance, event_bus)
    return extensions
