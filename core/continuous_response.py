#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ContinuousResponseGenerator component for Kingdom AI.
Provides real-time response generation and manages AI interactions.
"""

import asyncio
import logging
import time
from datetime import datetime

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class ContinuousResponseGenerator(BaseComponent):
    """
    Component for generating continuous AI responses.
    Maintains context and provides seamless conversation flow.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the ContinuousResponseGenerator component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus, config)
        self.name = "ContinuousResponseGenerator"
        self.description = "Manages real-time AI response generation"
        
        # Response configuration
        self.idle_threshold = self.config.get('idle_threshold', 30)  # seconds
        self.max_context_length = self.config.get('max_context_length', 10)
        self.response_delay = self.config.get('response_delay', 0.5)  # seconds
        self.response_types = self.config.get('response_types', ['text', 'voice'])
        
        # State management
        self.conversation_context = []
        self.last_interaction_time = time.time()
        self.is_generating = False
        self.is_paused = False
        self.last_query = None
        self.last_response = None
        self.idle_check_task = None
        self.user_info = {}
        self.thoth_available = False
        
        # Metrics
        self.response_count = 0
        self.avg_response_time = 0
        self.total_response_time = 0
        
    async def initialize(self):
        """Initialize the ContinuousResponseGenerator component."""
        logger.info("Initializing ContinuousResponseGenerator")
        
        # Subscribe to relevant events
        self.event_bus.subscribe("user.query", self.on_user_query)
        self.event_bus.subscribe("user.idle", self.on_user_idle)
        self.event_bus.subscribe("thoth.response", self.on_thoth_response)
        self.event_bus.subscribe("thoth.status", self.on_thoth_status)
        self.event_bus.subscribe("voice.input", self.on_voice_input)
        self.event_bus.subscribe("system.pause", self.on_system_pause)
        self.event_bus.subscribe("system.resume", self.on_system_resume)
        self.event_bus.subscribe("system.context.update", self.on_context_update)
        self.event_bus.subscribe("system.shutdown", self.on_shutdown)
        self.event_bus.subscribe("gui.user.info", self.on_user_info)
        self.event_bus.subscribe("thoth.available", self.on_thoth_available)
        
        # Start idle checking
        self.idle_check_task = asyncio.create_task(self.check_idle_status())
        
        logger.info("ContinuousResponseGenerator initialized")
        
        # Publish initialization event
        self.event_bus.publish("continuous_response.initialized", {
            "timestamp": datetime.now().isoformat()
        })
    
    async def check_idle_status(self):
        """Check if the user has been idle."""
        try:
            while True:
                if not self.is_paused:
                    current_time = time.time()
                    idle_time = current_time - self.last_interaction_time
                    
                    if idle_time >= self.idle_threshold and not self.is_generating:
                        # User has been idle, generate a proactive response
                        await self.generate_idle_response()
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
        except asyncio.CancelledError:
            logger.info("Idle status checking stopped")
        except Exception as e:
            logger.error(f"Error in idle status checking: {str(e)}")
    
    async def generate_idle_response(self):
        """Generate a response when the user is idle."""
        if not self.conversation_context or not self.thoth_available:
            return
        
        self.is_generating = True
        
        try:
            logger.info("Generating idle response")
            
            idle_context = {
                "type": "idle",
                "last_interaction": self.last_interaction_time,
                "idle_duration": time.time() - self.last_interaction_time,
                "conversation_context": self.conversation_context,
                "user_info": self.user_info,
                "timestamp": datetime.now().isoformat()
            }
            
            # Publish idle event
            self.event_bus.publish("user.idle", idle_context)
            
            # Ask ThothAI to generate a response
            self.event_bus.publish("thoth.generate", {
                "query_type": "idle",
                "context": self.conversation_context,
                "user_info": self.user_info,
                "generate_type": "suggestion",
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error generating idle response: {str(e)}")
            self.is_generating = False
    
    async def on_user_query(self, data):
        """
        Handle user query event.
        
        Args:
            data: User query data
        """
        self.last_interaction_time = time.time()
        query = data.get("query")
        query_type = data.get("type", "text")
        
        if not query:
            return
        
        self.last_query = query
        
        # Update context
        self.conversation_context.append({
            "role": "user",
            "content": query,
            "type": query_type,
            "timestamp": datetime.now().isoformat()
        })
        
        # Trim context if needed
        if len(self.conversation_context) > self.max_context_length:
            self.conversation_context = self.conversation_context[-self.max_context_length:]
        
        # Forward to ThothAI if available
        if self.thoth_available:
            self.is_generating = True
            
            self.event_bus.publish("thoth.generate", {
                "query": query,
                "query_type": query_type,
                "context": self.conversation_context,
                "user_info": self.user_info,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Forwarded user query to ThothAI: {query}")
        else:
            # SOTA 2026 FIX: ThothAI is optional - use debug not warning
            logger.debug("ℹ️ ThothAI not available for processing query (using fallback)")
            
            # Provide fallback response
            fallback_response = {
                "response": "I'm sorry, but the AI system is currently unavailable. Please try again later.",
                "response_type": "text",
                "source": "fallback",
                "timestamp": datetime.now().isoformat()
            }
            
            self.event_bus.publish("continuous_response.response", fallback_response)
            
            # Update context with fallback response
            self.conversation_context.append({
                "role": "assistant",
                "content": fallback_response["response"],
                "type": "text",
                "source": "fallback",
                "timestamp": datetime.now().isoformat()
            })
    
    async def on_thoth_response(self, data):
        """
        Handle ThothAI response event.
        
        Args:
            data: ThothAI response data
        """
        response = data.get("response")
        response_type = data.get("type", "text")
        processing_time = data.get("processing_time", 0)
        
        if not response:
            return
        
        self.is_generating = False
        self.last_response = response
        
        # Update metrics
        self.response_count += 1
        self.total_response_time += processing_time
        self.avg_response_time = self.total_response_time / self.response_count
        
        # Update context
        self.conversation_context.append({
            "role": "assistant",
            "content": response,
            "type": response_type,
            "source": "thoth",
            "timestamp": datetime.now().isoformat()
        })
        
        # Forward the response with a small delay to appear natural
        await asyncio.sleep(self.response_delay)
        
        # Publish generated response
        self.event_bus.publish("continuous_response.response", {
            "response": response,
            "response_type": response_type,
            "source": "thoth",
            "metrics": {
                "processing_time": processing_time,
                "avg_response_time": self.avg_response_time,
                "response_count": self.response_count
            },
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info("Published ThothAI response")
    
    async def on_thoth_status(self, data):
        """
        Handle ThothAI status event.
        
        Args:
            data: ThothAI status data
        """
        status = data.get("status")
        
        if status == "error":
            error = data.get("error")
            logger.error(f"ThothAI error: {error}")
            
            # Provide fallback response if we were waiting for one
            if self.is_generating:
                self.is_generating = False
                
                fallback_response = {
                    "response": "I'm sorry, but there was an error processing your request. Please try again.",
                    "response_type": "text",
                    "source": "fallback",
                    "error": error,
                    "timestamp": datetime.now().isoformat()
                }
                
                self.event_bus.publish("continuous_response.response", fallback_response)
                
                # Update context with fallback response
                self.conversation_context.append({
                    "role": "assistant",
                    "content": fallback_response["response"],
                    "type": "text",
                    "source": "fallback",
                    "timestamp": datetime.now().isoformat()
                })
    
    async def on_voice_input(self, data):
        """
        Handle voice input event.
        
        Args:
            data: Voice input data
        """
        text = data.get("text")
        
        if not text:
            return
        
        # Process as a user query
        await self.on_user_query({
            "query": text,
            "type": "voice",
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_system_pause(self, _):
        """Handle system pause event."""
        self.is_paused = True
        logger.info("ContinuousResponseGenerator paused")
    
    async def on_system_resume(self, _):
        """Handle system resume event."""
        self.is_paused = False
        self.last_interaction_time = time.time()  # Reset idle timer
        logger.info("ContinuousResponseGenerator resumed")
    
    async def on_context_update(self, data):
        """
        Handle context update event.
        
        Args:
            data: Context update data
        """
        context_update = data.get("context")
        clear_context = data.get("clear", False)
        
        if clear_context:
            self.conversation_context = []
            logger.info("Conversation context cleared")
        
        if context_update:
            # Add new context items
            if isinstance(context_update, list):
                self.conversation_context.extend(context_update)
            else:
                self.conversation_context.append(context_update)
                
            # Trim context if needed
            if len(self.conversation_context) > self.max_context_length:
                self.conversation_context = self.conversation_context[-self.max_context_length:]
                
            logger.info("Conversation context updated")
    
    async def on_user_info(self, data):
        """
        Handle user info event.
        
        Args:
            data: User info data
        """
        self.user_info = data
        logger.info("User info updated")
    
    async def on_thoth_available(self, data):
        """
        Handle ThothAI availability event.
        
        Args:
            data: ThothAI availability data
        """
        is_available = data.get("available", False)
        self.thoth_available = is_available
        
        if is_available:
            logger.info("ThothAI is now available")
        else:
            logger.warning("ThothAI is no longer available")
    
    async def on_user_idle(self, _):
        """Handle user idle event."""
        try:
            idle_duration = time.time() - self.last_interaction_time
            logger.debug("User idle event received (idle for %.1fs)", idle_duration)

            if not self.is_paused and not self.is_generating and self.thoth_available:
                if idle_duration >= self.idle_threshold:
                    await self.generate_idle_response()
        except Exception as e:
            logger.error("Error handling user idle event: %s", e)
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the ContinuousResponseGenerator component."""
        logger.info("Shutting down ContinuousResponseGenerator")
        
        # Cancel idle checking task
        if self.idle_check_task:
            self.idle_check_task.cancel()
            try:
                await self.idle_check_task
            except asyncio.CancelledError:
                pass
        
        # Clear context
        self.conversation_context = []
        
        logger.info("ContinuousResponseGenerator shut down successfully")
