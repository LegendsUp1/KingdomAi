"""
AI Response Coordinator - Coordinates AI responses to prevent duplicates.

This module ensures only one AI response is generated per user request,
eliminating the "double chat" issue where multiple AI systems respond.
"""

import logging
import asyncio
import uuid
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class AIResponseCoordinator:
    """Coordinates AI responses to prevent duplicates."""
    
    def __init__(self, event_bus):
        """Initialize the AI Response Coordinator.
        
        Args:
            event_bus: Event bus for component communication
        """
        self.event_bus = event_bus
        self.logger = logger
        self.active_requests = {}
        self.response_lock = asyncio.Lock()
        self.primary_ai_handler = None
        
    def set_primary_ai_handler(self, handler: Callable):
        """Set the primary AI handler function.
        
        Args:
            handler: Async function that takes (message, context) and returns response
        """
        self.primary_ai_handler = handler
        self.logger.info("✅ Primary AI handler registered")
    
    async def handle_ai_request(self, request_id: str, message: str, context: dict = None) -> dict:
        """Handle AI request with deduplication.
        
        Args:
            request_id: Unique request ID
            message: User message
            context: Optional context dict
            
        Returns:
            Dict with response and metadata
        """
        if context is None:
            context = {}
        
        async with self.response_lock:
            # Check if request already being processed
            if request_id in self.active_requests:
                status = self.active_requests[request_id]['status']
                if status == 'processing':
                    self.logger.warning(f"Request {request_id} already processing, skipping duplicate")
                    return {
                        'status': 'duplicate',
                        'message': 'Request already being processed'
                    }
                elif status == 'completed':
                    self.logger.info(f"Returning cached response for {request_id}")
                    return self.active_requests[request_id]['response']
            
            # Mark request as active
            self.active_requests[request_id] = {
                'status': 'processing',
                'timestamp': datetime.now(),
                'message': message
            }
        
        try:
            # Get response from primary AI system
            if self.primary_ai_handler:
                self.logger.info(f"Processing request {request_id} with primary AI handler")
                response_text = await self.primary_ai_handler(message, context)
            else:
                self.logger.warning("No primary AI handler registered, using fallback")
                response_text = await self._fallback_response(message, context)
            
            response = {
                'status': 'success',
                'response': response_text,
                'request_id': request_id,
                'timestamp': datetime.now().isoformat(),
                'source': 'kingdom_ai_primary'
            }
            
            # Update active requests
            async with self.response_lock:
                self.active_requests[request_id] = {
                    'status': 'completed',
                    'response': response,
                    'timestamp': datetime.now()
                }
            
            # Publish to ai.response (UnifiedAIRouter will deduplicate → ai.response.unified)
            self.event_bus.publish('ai.response', response)
            
            # Schedule cleanup
            asyncio.create_task(self._cleanup_request(request_id, delay=60))
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing AI request {request_id}: {e}")
            
            error_response = {
                'status': 'error',
                'error': str(e),
                'request_id': request_id,
                'timestamp': datetime.now().isoformat()
            }
            
            # Update active requests
            async with self.response_lock:
                self.active_requests[request_id] = {
                    'status': 'error',
                    'response': error_response,
                    'timestamp': datetime.now()
                }
            
            # Schedule cleanup
            asyncio.create_task(self._cleanup_request(request_id, delay=60))
            
            return error_response
    
    async def _fallback_response(self, message: str, context: dict) -> str:
        """Generate fallback response when no primary handler is available.
        
        Args:
            message: User message
            context: Context dict
            
        Returns:
            Fallback response text
        """
        return f"I received your message: '{message[:50]}...' but the primary AI handler is not available. Please ensure the AI system is properly initialized."
    
    async def _cleanup_request(self, request_id: str, delay: int):
        """Clean up completed request after delay.
        
        Args:
            request_id: Request ID to clean up
            delay: Delay in seconds before cleanup
        """
        await asyncio.sleep(delay)
        async with self.response_lock:
            if request_id in self.active_requests:
                del self.active_requests[request_id]
                self.logger.debug(f"Cleaned up request {request_id}")
    
    def generate_request_id(self) -> str:
        """Generate unique request ID.
        
        Returns:
            Unique request ID string
        """
        return f"ai_req_{uuid.uuid4().hex[:12]}_{int(datetime.now().timestamp() * 1000)}"
    
    async def get_active_requests_count(self) -> int:
        """Get count of active requests.
        
        Returns:
            Number of active requests
        """
        async with self.response_lock:
            return len(self.active_requests)
    
    async def cancel_request(self, request_id: str) -> bool:
        """Cancel an active request.
        
        Args:
            request_id: Request ID to cancel
            
        Returns:
            True if cancelled, False if not found
        """
        async with self.response_lock:
            if request_id in self.active_requests:
                self.active_requests[request_id]['status'] = 'cancelled'
                self.logger.info(f"Cancelled request {request_id}")
                return True
            return False
