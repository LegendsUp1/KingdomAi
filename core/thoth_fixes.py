#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Thoth AI System Fixes

This file contains the fixes for the Thoth AI System tests, including:
1. Implementation of the missing _register_event_handlers method
2. Implementation of the missing _handle_code_generation method
3. Fixes for event bus communication issues
"""

async def _register_event_handlers(self):
    """Register event handlers with the event bus.
    
    This method subscribes to all relevant events for the MCPConnector.
    """
    self.logger.info("Registering event handlers with event bus")
    
    try:
        # System events
        await self.event_bus.subscribe("system.health.query", self._handle_health_query)
        
        # AI model discovery and management
        await self.event_bus.subscribe("ai.discover.models", self._handle_model_discovery)
        await self.event_bus.subscribe("ai.models.discover", self._handle_model_discovery)  # Alternative event name
        
        # AI consultation and code generation
        await self.event_bus.subscribe("ai.consult", self._handle_model_consultation)
        await self.event_bus.subscribe("ai.code", self._handle_code_generation)  # Add missing code event handler
        
        # Start periodic status updates
        asyncio.create_task(self._periodic_status_update())
        
        self.logger.info("Event handlers successfully registered")
        return True
    except Exception as e:
        self.logger.error(f"Error registering event handlers: {str(e)}")
        self.logger.error(traceback.format_exc())
        return False

async def _handle_code_generation(self, data):
    """Handle ai.code events for code generation.
    
    Args:
        data: Event data containing the code prompt and other parameters
    """
    self.logger.info("Handling code generation request")
    
    # Ensure data is a dictionary
    if not isinstance(data, dict):
        data = {}
        
    # Extract parameters
    request_id = data.get('request_id', str(uuid.uuid4()))
    prompt = data.get('prompt', '')
    language = data.get('language', 'python')
    timeout = data.get('timeout', 30)
    
    if not prompt:
        self.logger.error("Empty prompt in code generation request")
        if self.event_bus:
            await self.event_bus.publish("ai.code.response", {
                "status": "error",
                "error": "Empty prompt",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            })
        return
        
    self.logger.info(f"Generating code for prompt: {prompt[:50]}...")
    
    try:
        # Use a code-capable model if available
        available_models = []
        if hasattr(self, 'model_capabilities'):
            for model, capabilities in self.model_capabilities.items():
                if "code" in capabilities:
                    available_models.append(model)
                    
        # If no code-capable models found, use any model
        if not available_models and hasattr(self, 'active_models'):
            available_models = list(self.active_models.keys())
            
        # If still no models available, use default
        if not available_models:
            available_models = ["codellama"]
            
        # Select the first available model
        model_to_use = available_models[0] if available_models else "codellama"
            
        # Format code-specific prompt
        formatted_prompt = f"Generate {language} code for the following task. Respond with ONLY the code, no explanations:\n\n{prompt}"
        
        # Generate code completion
        response = await self.generate_completion(model_to_use, formatted_prompt)
        
        # Extract code from the response
        code = self._extract_code_from_response(response, language) if hasattr(self, '_extract_code_from_response') else response
        
        # Publish the code response with the expected format
        if self.event_bus:
            await self.event_bus.publish("ai.code.response", {
                "status": "success",
                "code": code,
                "language": language,
                "model": model_to_use,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            })
            
        self.logger.info(f"Code generation complete using {model_to_use}")
        return {
            "status": "success",
            "code": code,
            "language": language,
            "model": model_to_use
        }
            
    except Exception as e:
        self.logger.error(f"Error in code generation: {str(e)}")
        self.logger.error(traceback.format_exc())
        
        # Publish error response
        if self.event_bus:
            await self.event_bus.publish("ai.code.response", {
                "status": "error",
                "error": str(e),
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            })
"""
Notes for implementing these fixes:

1. Add these methods to the MCPConnector class in core/thoth.py
2. Ensure that _register_event_handlers is called during initialization
3. Fix any other issues with event naming mismatches
"""
