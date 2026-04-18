"""
IntentRecognition module for Kingdom AI system.
"""

import logging
import json
import re
import os
from typing import Dict, Any, Tuple
from datetime import datetime

class IntentRecognition:
    """
    Intent recognition system for the Kingdom AI.
    Identifies user intents from text and voice input to trigger appropriate actions.
    """
    
    def __init__(self, event_bus=None, config=None, thoth_ai=None):
        """Initialize the intent recognition system."""
        self.event_bus = event_bus
        self.config = config or {}
        self.thoth_ai = thoth_ai
        self.logger = logging.getLogger("IntentRecognition")
        
        # Intent definitions
        self.intents = {}
        self.fallback_threshold = self.config.get("fallback_threshold", 0.3)
        self.min_confidence = self.config.get("min_confidence", 0.6)
        
        # Intent history
        self.intent_history = []
        self.max_history_size = self.config.get("max_history_size", 100)
        
        # Load default intents
        self._load_default_intents()
        
    async def initialize(self):
        """Initialize the intent recognition system."""
        try:
            self.logger.info("Initializing Intent Recognition System")
            
            # Load custom intents if available
            intents_file = self.config.get("intents_file", "config/intents.json")
            if os.path.exists(intents_file):
                try:
                    with open(intents_file, 'r') as f:
                        custom_intents = json.load(f)
                        # Merge with existing intents, overwriting defaults
                        self.intents.update(custom_intents)
                        self.logger.info(f"Loaded {len(custom_intents)} custom intents")
                except Exception as e:
                    self.logger.error(f"Error loading custom intents: {e}")
            
            # Register event handlers
            if self.event_bus:
                await self.event_bus.subscribe_sync("intent.recognize", self.handle_recognize_intent)
                await self.event_bus.subscribe_sync("intent.register", self.handle_register_intent)
                await self.event_bus.subscribe_sync("intent.unregister", self.handle_unregister_intent)
                await self.event_bus.subscribe_sync("intent.get", self.handle_get_intents)
                await self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
                self.logger.info("Intent Recognition event handlers registered")
            
            self.logger.info(f"Intent Recognition System initialized with {len(self.intents)} intents")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing Intent Recognition System: {e}")
            return False
    
    def _load_default_intents(self):
        """Load default intents for common actions."""
        # Trading intents
        self.intents["trade"] = {
            "patterns": [
                "trade (\w+)",
                "buy (\w+)",
                "sell (\w+)",
                "place an order for (\w+)",
                "execute (\w+) trade"
            ],
            "action": "trading.execute_trade",
            "params": ["symbol"],
            "examples": ["trade BTC", "buy ETH", "sell DOGE"]
        }
        
        # Market information intents
        self.intents["market_info"] = {
            "patterns": [
                "price of (\w+)",
                "how much is (\w+) worth",
                "what is (\w+) trading at",
                "(\w+) market data",
                "(\w+) price"
            ],
            "action": "market.get_price",
            "params": ["symbol"],
            "examples": ["price of BTC", "how much is ETH worth", "BTC market data"]
        }
        
        # Prediction intents
        self.intents["prediction"] = {
            "patterns": [
                "predict (\w+)",
                "forecast for (\w+)",
                "what will (\w+) do",
                "(\w+) prediction",
                "analyze (\w+) trend"
            ],
            "action": "prediction.market",
            "params": ["symbol"],
            "examples": ["predict BTC", "forecast for ETH", "BTC prediction"]
        }
        
        # Mining intents
        self.intents["mining"] = {
            "patterns": [
                "start mining",
                "stop mining",
                "mining status",
                "how is mining going",
                "mining stats"
            ],
            "action": "mining.command",
            "params": ["command"],
            "examples": ["start mining", "stop mining", "mining status"]
        }
        
        # System intents
        self.intents["system"] = {
            "patterns": [
                "system status",
                "health check",
                "restart system",
                "shutdown",
                "system information"
            ],
            "action": "system.command",
            "params": ["command"],
            "examples": ["system status", "health check", "system information"]
        }
        
        # Help intent
        self.intents["help"] = {
            "patterns": [
                "help",
                "help me",
                "what can you do",
                "show commands",
                "available commands"
            ],
            "action": "system.help",
            "params": [],
            "examples": ["help", "what can you do", "show commands"]
        }
        
        self.logger.info(f"Loaded {len(self.intents)} default intents")
    
    async def handle_recognize_intent(self, data):
        """Handle request to recognize intent from text."""
        try:
            if not data or "text" not in data:
                await self._publish_error("recognize_intent", "No text provided")
                return
                
            # Extract text
            text = data.get("text").strip().lower()
            source = data.get("source", "text")
            
            # Recognize intent
            intent, confidence, params = await self._recognize_intent(text)
            
            # Add to history
            self.intent_history.append({
                "text": text,
                "intent": intent,
                "confidence": confidence,
                "params": params,
                "source": source,
                "timestamp": datetime.now().isoformat()
            })
            
            # Trim history if needed
            if len(self.intent_history) > self.max_history_size:
                self.intent_history = self.intent_history[-self.max_history_size:]
            
            # Publish intent recognition result
            result = {
                "text": text,
                "intent": intent,
                "confidence": confidence,
                "params": params,
                "timestamp": datetime.now().isoformat()
            }
            
            if self.event_bus:
                await self.event_bus.publish("intent.recognized", result)
                
                # If confidence is high enough, trigger the associated action
                if confidence >= self.min_confidence and intent != "fallback":
                    intent_def = self.intents.get(intent, {})
                    action = intent_def.get("action")
                    if action:
                        await self.event_bus.publish(action, {
                            "intent": intent,
                            "text": text,
                            "params": params,
                            "confidence": confidence,
                            "source": source
                        })
                        self.logger.info(f"Triggered action {action} for intent {intent}")
            
        except Exception as e:
            self.logger.error(f"Error recognizing intent: {e}")
            await self._publish_error("recognize_intent", str(e))
    
    async def _recognize_intent(self, text: str) -> Tuple[str, float, Dict[str, Any]]:
        """
        Recognize intent from text.
        
        Args:
            text: Input text
            
        Returns:
            Tuple of (intent_name, confidence, params)
        """
        # This is a simplified rule-based implementation
        # In a real system, this would use more sophisticated NLP
        
        # Default values
        best_intent = "fallback"
        best_confidence = 0.0
        best_params = {}
        
        # Try to match against each intent
        for intent_name, intent_def in self.intents.items():
            patterns = intent_def.get("patterns", [])
            
            for pattern in patterns:
                # Try to match the pattern
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Calculate confidence based on ratio of matched text to total text
                    match_start, match_end = match.span()
                    match_length = match_end - match_start
                    
                    # Base confidence on match coverage
                    confidence = min(0.95, match_length / len(text) + 0.3)
                    
                    # Extract parameters
                    params = {}
                    param_names = intent_def.get("params", [])
                    
                    for i, param_name in enumerate(param_names):
                        if i + 1 <= len(match.groups()):
                            params[param_name] = match.group(i + 1)
                    
                    # Check if this is better than current best
                    if confidence > best_confidence:
                        best_intent = intent_name
                        best_confidence = confidence
                        best_params = params
        
        # If using ThothAI and confidence is low, try to get a better result
        if self.thoth_ai and best_confidence < self.min_confidence:
            try:
                # Use Ollama for real intent recognition
                import aiohttp
                import json
                
                # Prepare prompt for intent recognition
                intent_prompt = f"""Analyze the following user input and identify the intent. 
Return only the intent name and confidence (0.0-1.0) as JSON: {{"intent": "...", "confidence": 0.0}}

Available intents: {', '.join(self.intents.keys())}

User input: "{text}"

JSON response:"""
                
                # Call Ollama API
                async def call_ollama():
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                "http://localhost:11434/api/generate",
                                json={
                                    "model": "llama3.2",  # or other available model
                                    "prompt": intent_prompt,
                                    "stream": False,
                                    "options": {"temperature": 0.3}
                                },
                                timeout=aiohttp.ClientTimeout(total=10)
                            ) as resp:
                                if resp.status == 200:
                                    result = await resp.json()
                                    response_text = result.get("response", "")
                                    
                                    # Parse JSON from response
                                    try:
                                        # Extract JSON from response text
                                        import re
                                        json_match = re.search(r'\{[^}]+\}', response_text)
                                        if json_match:
                                            ai_result = json.loads(json_match.group())
                                            ai_intent = ai_result.get("intent", best_intent)
                                            ai_confidence = float(ai_result.get("confidence", best_confidence))
                                            
                                            # Use AI result if confidence is higher
                                            if ai_confidence > best_confidence and ai_intent in self.intents:
                                                return ai_intent, ai_confidence, best_params
                                    except (json.JSONDecodeError, ValueError) as e:
                                        self.logger.debug(f"Could not parse Ollama response: {e}")
                    except Exception as e:
                        self.logger.debug(f"Ollama API call failed: {e}")
                    return None
                
                # Try to get better result from Ollama
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If loop is running, schedule the call
                        task = asyncio.create_task(call_ollama())
                        # Don't wait - use existing result
                    else:
                        ai_result = loop.run_until_complete(call_ollama())
                        if ai_result:
                            ai_intent, ai_confidence, ai_params = ai_result
                            if ai_confidence > best_confidence:
                                return ai_intent, ai_confidence, ai_params
                except RuntimeError:
                    # No event loop - skip Ollama call
                    pass
            except ImportError:
                self.logger.debug("aiohttp not available for Ollama integration")
            except Exception as e:
                self.logger.error(f"Error using ThothAI/Ollama for intent recognition: {e}")
        
        # If confidence is below threshold, use fallback
        if best_confidence < self.fallback_threshold:
            best_intent = "fallback"
            best_confidence = 0.2
            best_params = {}
        
        return best_intent, best_confidence, best_params
    
    async def handle_register_intent(self, data):
        """Handle request to register a new intent."""
        try:
            if not data or "intent" not in data:
                await self._publish_error("register_intent", "No intent data provided")
                return
                
            intent_name = data.get("intent")
            intent_def = data.get("definition", {})
            
            # Validate intent definition
            if not intent_def:
                await self._publish_error("register_intent", "Empty intent definition")
                return
                
            if "patterns" not in intent_def or not intent_def["patterns"]:
                await self._publish_error("register_intent", "Intent definition must include patterns")
                return
                
            # Register the intent
            self.intents[intent_name] = intent_def
            
            # Publish confirmation
            if self.event_bus:
                await self.event_bus.publish("intent.registered", {
                    "intent": intent_name,
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.info(f"Registered new intent: {intent_name}")
            
        except Exception as e:
            self.logger.error(f"Error registering intent: {e}")
            await self._publish_error("register_intent", str(e))
    
    async def handle_unregister_intent(self, data):
        """Handle request to unregister an intent."""
        try:
            if not data or "intent" not in data:
                await self._publish_error("unregister_intent", "No intent name provided")
                return
                
            intent_name = data.get("intent")
            
            # Check if intent exists
            if intent_name not in self.intents:
                await self._publish_error("unregister_intent", f"Intent {intent_name} not found")
                return
                
            # Remove the intent
            del self.intents[intent_name]
            
            # Publish confirmation
            if self.event_bus:
                await self.event_bus.publish("intent.unregistered", {
                    "intent": intent_name,
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                })
                
            self.logger.info(f"Unregistered intent: {intent_name}")
            
        except Exception as e:
            self.logger.error(f"Error unregistering intent: {e}")
            await self._publish_error("unregister_intent", str(e))
    
    async def handle_get_intents(self, data=None):
        """Handle request to get available intents."""
        try:
            # Extract filters if any
            intent_name = data.get("intent") if data else None
            
            # Prepare results
            result = {}
            
            if intent_name:
                # Get specific intent
                if intent_name in self.intents:
                    result = {
                        "intent": intent_name,
                        "definition": self.intents[intent_name]
                    }
                else:
                    await self._publish_error("get_intents", f"Intent {intent_name} not found")
                    return
            else:
                # Get all intents
                result = {
                    "intents": self.intents
                }
            
            # Publish results
            if self.event_bus:
                await self.event_bus.publish("intent.get_result", {
                    **result,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error getting intents: {e}")
            await self._publish_error("get_intents", str(e))
    
    async def handle_shutdown(self, data=None):
        """Handle system shutdown event."""
        try:
            self.logger.info("Shutting down Intent Recognition System")
            
            # Save custom intents
            intents_file = self.config.get("intents_file", "config/intents.json")
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(intents_file), exist_ok=True)
                
                with open(intents_file, 'w') as f:
                    json.dump(self.intents, f, indent=2)
                    
                self.logger.info(f"Saved intents to {intents_file}")
            except Exception as e:
                self.logger.error(f"Error saving intents: {e}")
            
            self.logger.info("Intent Recognition System shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during Intent Recognition System shutdown: {e}")
    
    async def _publish_error(self, operation, error_message):
        """Publish an error message to the event bus."""
        if self.event_bus:
            await self.event_bus.publish("intent.error", {
                "operation": operation,
                "error": error_message,
                "timestamp": datetime.now().isoformat()
            })
