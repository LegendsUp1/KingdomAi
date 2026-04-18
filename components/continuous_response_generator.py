#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Continuous Response Generator Component
"""

import os
import sys
import time
import json
import random
import secrets
import logging
import threading
import collections
from typing import Dict, Any, List, Optional, Union, Callable

# Configure logging
logger = logging.getLogger('kingdom_ai.continuous_response')

class ContinuousResponseGenerator:
    """Maintains conversation flow with prioritized response queues.
    
    This class ensures natural conversation flow is maintained even during
    background operations by providing appropriate responses, acknowledgments,
    and idle phrases when needed to prevent timeouts.
    """
    
    def __init__(self, event_bus, config=None):
        """Initialize the continuous response generator.
        
        Args:
            event_bus: System event bus for communication
            config: Configuration dictionary
        """
        self.event_bus = event_bus
        self.config = config or {}
        self.running = False
        
        # Response queue configuration
        self.max_queue_size = self.config.get("max_response_queue_size", 100)
        self.idle_response_interval = self.config.get("idle_response_interval", 15.0)  # 15 seconds
        self.thinking_response_interval = self.config.get("thinking_response_interval", 3.0)  # 3 seconds
        
        # Response queues with priority
        self.response_queues = {
            "critical": collections.deque(maxlen=self.max_queue_size),  # Priority 1 (highest)
            "high": collections.deque(maxlen=self.max_queue_size),      # Priority 2
            "normal": collections.deque(maxlen=self.max_queue_size),    # Priority 3
            "low": collections.deque(maxlen=self.max_queue_size),       # Priority 4
            "idle": collections.deque(maxlen=self.max_queue_size)       # Priority 5 (lowest)
        }
        
        # Response tracking
        self.last_response_time = time.time()
        self.conversation_active = False
        self.is_thinking = False
        
        # Load response templates
        self._load_response_templates()
        
        # Threads for background processing
        self.response_thread = None
        self.response_lock = threading.RLock()
        
        # Register event handlers
        self._register_events()
        
        logger.info("Continuous Response Generator initialized successfully")
        self.running = True
        
        # Start background processing
        self._start_background_processing()
    
    def _register_events(self):
        """Register event handlers for conversation-related events."""
        try:
            if self.event_bus:
                self.event_bus.subscribe("user.input", self._handle_user_input)
                self.event_bus.subscribe("system.thinking", self._handle_thinking_state)
                self.event_bus.subscribe("system.response", self._handle_system_response)
                logger.debug("Continuous Response Generator event handlers registered")
        except Exception as e:
            logger.error(f"Failed to register Continuous Response Generator event handlers: {str(e)}")
    
    def _load_response_templates(self):
        """Load response templates from configuration or use defaults."""
        # Default templates
        self.response_templates = {
            "acknowledgment": [
                "I got that.",
                "I understand.",
                "Processing your request.",
                "Working on it.",
                "I hear you.",
                "Got it.",
                "On it.",
                "I'll take care of that.",
                "Understood.",
                "Processing."
            ],
            "thinking": [
                "Let me think about that...",
                "Processing...",
                "Analyzing...",
                "Computing...",
                "Working on that...",
                "Thinking...",
                "Calculating...",
                "Still working...",
                "This requires some thought...",
                "Processing your request..."
            ],
            "idle": [
                "I'm still here if you need anything.",
                "Feel free to ask me something else.",
                "Is there anything else I can help with?",
                "I'm ready when you are.",
                "Let me know if you need anything else.",
                "Anything else on your mind?",
                "Standing by for your next request.",
                "I'm available for further assistance.",
                "Waiting for your next command.",
                "Ready for your next question."
            ]
        }
        
        # Try to load custom templates from config
        custom_templates = self.config.get("response_templates", {})
        for category, phrases in custom_templates.items():
            if phrases and isinstance(phrases, list):
                self.response_templates[category] = phrases
    
    def _select_random_phrase(self, category):
        """Select a random phrase from a category using secure randomness.
        
        Args:
            category: Category of phrase to select
            
        Returns:
            str: Selected phrase
        """
        phrases = self.response_templates.get(category, [])
        if not phrases:
            return ""
            
        # Use cryptographically secure random selection
        index = secrets.randbelow(len(phrases))
        return phrases[index]
    
    def _start_background_processing(self):
        """Start background thread for processing responses."""
        self.response_thread = threading.Thread(
            target=self._process_responses,
            name="ContinuousResponseGenerator"
        )
        self.response_thread.daemon = True
        self.response_thread.start()
        logger.debug("Started background response processing thread")
    
    def _process_responses(self):
        """Background thread for processing response queue and generating idle responses."""
        last_idle_check = time.time()
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check if we need to send an idle response
                if (self.conversation_active and 
                    current_time - self.last_response_time > self.idle_response_interval and
                    current_time - last_idle_check > self.idle_response_interval):
                    
                    # Send idle response if no activity
                    self._send_idle_response()
                    last_idle_check = current_time
                
                # Check if we're in thinking state and need to send a thinking response
                if (self.is_thinking and 
                    current_time - self.last_response_time > self.thinking_response_interval):
                    
                    # Send thinking response
                    self._send_thinking_response()
                
                # Process any queued responses
                next_response = self._get_next_response()
                if next_response:
                    self._send_response(next_response)
                
                # Small sleep to prevent excessive CPU usage
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in response processing thread: {str(e)}")
                # Continue running despite errors
                time.sleep(1.0)
    
    def _get_next_response(self):
        """Get the next highest priority response from the queues.
        
        Returns:
            dict: Next response or None if queues are empty
        """
        with self.response_lock:
            # Check queues in priority order
            for priority in ["critical", "high", "normal", "low", "idle"]:
                queue = self.response_queues[priority]
                if queue:
                    return queue.popleft()
            
            return None
    
    def add_response(self, response, priority="normal"):
        """Add a response to the appropriate priority queue.
        
        Args:
            response: Response content (str or dict)
            priority: Priority level (critical, high, normal, low, idle)
        """
        if priority not in self.response_queues:
            priority = "normal"
            
        # Normalize response to dictionary format
        if isinstance(response, str):
            response_dict = {"text": response, "priority": priority, "timestamp": time.time()}
        else:
            response_dict = response
            response_dict.setdefault("priority", priority)
            response_dict.setdefault("timestamp", time.time())
            
        with self.response_lock:
            self.response_queues[priority].append(response_dict)
            logger.debug(f"Added {priority} response to queue: {response_dict.get('text', '')[:30]}...")
    
    def _send_response(self, response):
        """Send a response through the event bus.
        
        Args:
            response: Response dictionary to send
        """
        try:
            self.last_response_time = time.time()
            
            # Publish response event
            if self.event_bus:
                self.event_bus.publish("system.response", {
                    "text": response.get("text", ""),
                    "type": response.get("type", "text"),
                    "priority": response.get("priority", "normal"),
                    "source": "continuous_response_generator"
                })
                
            logger.debug(f"Sent response: {response.get('text', '')[:30]}...")
            
        except Exception as e:
            logger.error(f"Error sending response: {str(e)}")
    
    def _send_idle_response(self):
        """Send an idle response to maintain conversation flow."""
        idle_phrase = self._select_random_phrase("idle")
        if idle_phrase:
            self.add_response({
                "text": idle_phrase,
                "type": "idle",
                "priority": "idle",
                "timestamp": time.time()
            })
    
    def _send_thinking_response(self):
        """Send a thinking response while processing complex requests."""
        thinking_phrase = self._select_random_phrase("thinking")
        if thinking_phrase:
            self.add_response({
                "text": thinking_phrase,
                "type": "thinking",
                "priority": "normal",
                "timestamp": time.time()
            })
    
    def _send_acknowledgment(self):
        """Send an acknowledgment for user input."""
        ack_phrase = self._select_random_phrase("acknowledgment")
        if ack_phrase:
            self.add_response({
                "text": ack_phrase,
                "type": "acknowledgment",
                "priority": "high",
                "timestamp": time.time()
            })
    
    def _handle_user_input(self, event):
        """Handle user input events."""
        try:
            # Mark conversation as active
            self.conversation_active = True
            self.last_response_time = time.time()
            
            # Send acknowledgment response occasionally (30% chance)
            if secrets.randbelow(10) < 3:  # 30% chance
                self._send_acknowledgment()
                
        except Exception as e:
            logger.error(f"Error handling user input event: {str(e)}")
    
    def _handle_thinking_state(self, event):
        """Handle system thinking state changes."""
        try:
            # Update thinking state
            self.is_thinking = event.get("thinking", False)
            
            if self.is_thinking:
                # Send initial thinking response
                self._send_thinking_response()
                
        except Exception as e:
            logger.error(f"Error handling thinking state event: {str(e)}")
    
    def _handle_system_response(self, event):
        """Handle system response events."""
        try:
            # Update last response time
            self.last_response_time = time.time()
            
            # If this is a final response, exit thinking state
            if event.get("final", False):
                self.is_thinking = False
                
        except Exception as e:
            logger.error(f"Error handling system response event: {str(e)}")
    
    def shutdown(self):
        """Shut down the continuous response generator cleanly."""
        logger.info("Shutting down Continuous Response Generator")
        self.running = False
        
        # Wait for background thread to finish
        if self.response_thread and self.response_thread.is_alive():
            self.response_thread.join(timeout=1.0)
