"""ThothAI Implementation for Kingdom AI

Provides AI capabilities through Ollama integration.
"""

import os
import logging
import asyncio
import httpx

logger = logging.getLogger("ThothAI")

class ThothAI:
    """ThothAI implementation for Ollama integration."""

    def __init__(self, event_bus=None, config=None):
        """Initialize the ThothAI instance."""
        self.event_bus = event_bus
        self.config = config or {}
        self.initialized = False
        self.ollama_base_url = self.config.get("ollama_url", "http://localhost:11434")
        self.default_model = self.config.get("model", "llama2")
        self.client = httpx.AsyncClient(timeout=60.0)
        logger.info(f"ThothAI initialized with Ollama URL: {self.ollama_base_url}")

    async def initialize(self):
        """Initialize and verify the Ollama connection."""
        logger.info("Initializing ThothAI...")

        if self.event_bus:
            # Subscribe to events
            await self.event_bus.subscribe("request_ai_completion", self.handle_completion_request)
            await self.event_bus.subscribe("request_ai_code", self.handle_code_request)
            logger.info("ThothAI subscribed to events")

        # Test connection to Ollama
        try:
            response = await self.client.get(f"{self.ollama_base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                logger.info(f"Connected to Ollama API successfully. Available models: {len(models)}")
                self.initialized = True
            else:
                logger.error(f"Error connecting to Ollama API: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Error connecting to Ollama API: {e}")

        return self.initialized

    async def get_completion(self, params):
        """Get completion from Ollama API."""
        model = params.get("model", self.default_model)
        prompt = params.get("prompt", "")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={"model": model, "prompt": prompt}
                )
                if response.status_code == 200:
                    return response.json().get("response")
                else:
                    logger.error(f"Ollama API error: {response.text}")
        except Exception as e:
            logger.error(f"Error getting completion: {e}")
        return None

    async def handle_completion_request(self, event_data):
        """Handle AI completion request."""
        try:
            prompt = event_data.get("prompt", "")
            model = event_data.get("model", self.default_model)
            response = await self.get_completion({"prompt": prompt, "model": model})

            if self.event_bus:
                await self.event_bus.publish("ai_completion_response", {
                    "response": response,
                    "request_id": event_data.get("request_id")
                })
        except Exception as e:
            logger.error(f"Error handling completion request: {e}")
            if self.event_bus:
                await self.event_bus.publish("ai_completion_error", {
                    "error": str(e),
                    "request_id": event_data.get("request_id")
                })

    async def handle_code_request(self, event_data):
        """Handle AI code generation request."""
        try:
            prompt = event_data.get("prompt", "")
            language = event_data.get("language", "python")
            model = event_data.get("model", self.default_model)

            # Add language context to the prompt
            enhanced_prompt = f"Generate {language} code for: {prompt}\nOnly provide the code with no explanations."
            response = await self.get_completion({"prompt": enhanced_prompt, "model": model})

            if self.event_bus:
                await self.event_bus.publish("ai_code_response", {
                    "code": response,
                    "language": language,
                    "request_id": event_data.get("request_id")
                })
        except Exception as e:
            logger.error(f"Error handling code request: {e}")
            if self.event_bus:
                await self.event_bus.publish("ai_code_error", {
                    "error": str(e),
                    "request_id": event_data.get("request_id")
                })
