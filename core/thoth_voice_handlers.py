"""
Thoth Voice Handlers Module

This module contains all voice-related handler methods and utility functions 
for the MCPConnector class that handles AI voice interactions.
"""

import asyncio
import traceback
import uuid
from datetime import datetime

class VoiceHandlers:
    """Voice handler methods to be integrated with MCPConnector class"""
    
    async def _handle_voice_toggle(self, data):
        """Handle voice toggle event from event bus.
        
        Args:
            data: Event data for voice toggle
        """
        try:
            if not isinstance(data, dict):
                self.logger.error("Invalid voice toggle data: not a dictionary")
                return
                
            enabled = data.get('enabled', True)  # Default to enabling voice
            request_id = data.get('request_id', str(uuid.uuid4()))
            
            self.logger.info(f"Voice {'enabled' if enabled else 'disabled'}")
            
            # Set voice enabled flag
            self.voice_enabled = enabled
            
            # Publish response
            if self.event_bus:
                await self.event_bus.publish("voice.toggle.response", {
                    "success": True,
                    "enabled": self.voice_enabled,
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error handling voice toggle: {str(e)}")
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
                
                await self.event_bus.publish("voice.toggle.response", error_data)

    async def _handle_voice_listen(self, data):
        """Handle voice listen event from event bus to activate voice recognition.
        
        Args:
            data: Event data for voice listen request
        """
        try:
            if not isinstance(data, dict):
                self.logger.error("Invalid voice listen data: not a dictionary")
                return
                
            request_id = data.get('request_id', str(uuid.uuid4()))
            timeout = data.get('timeout', 10.0)  # Default timeout in seconds
            
            self.logger.info(f"Listening for voice input (timeout: {timeout}s)")
            
            # Check if voice is enabled
            if not getattr(self, 'voice_enabled', False):
                self.logger.warning("Voice recognition requested but voice is disabled")
                if self.event_bus:
                    await self.event_bus.publish("voice.listen.response", {
                        "success": False,
                        "error": "Voice recognition is disabled",
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
                return
                
            try:
                import urllib.request
                import json as _json
                try:
                    from core.ollama_gateway import get_ollama_url
                    base = get_ollama_url()
                except ImportError:
                    base = "http://localhost:11434"
                req_body = _json.dumps({
                    "model": getattr(self, "voice_model", "whisper"),
                    "prompt": "Transcribe the following audio input.",
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{base}/api/generate",
                    data=req_body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result_data = _json.loads(resp.read().decode("utf-8"))
                transcript = result_data.get("response", "").strip()
                if self.event_bus:
                    await self.event_bus.publish("voice.listen.response", {
                        "success": bool(transcript),
                        "transcript": transcript or "Voice recognition returned empty result",
                        "confidence": 1.0 if transcript else 0.0,
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
            except Exception as voice_err:
                self.logger.warning(f"Voice recognition unavailable: {voice_err}")
                if self.event_bus:
                    await self.event_bus.publish("voice.listen.response", {
                        "success": False,
                        "transcript": "",
                        "error": "Voice recognition unavailable - no speech-to-text backend configured",
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
                
        except Exception as e:
            self.logger.error(f"Error handling voice listen: {str(e)}")
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
                
                await self.event_bus.publish("voice.listen.response", error_data)

    async def _handle_voice_command(self, data):
        """Handle voice command event from event bus.
        
        Args:
            data: Event data for voice command
        """
        try:
            if not isinstance(data, dict):
                self.logger.error("Invalid voice command data: not a dictionary")
                return
                
            command = data.get('command', '')
            request_id = data.get('request_id', str(uuid.uuid4()))
            
            if not command:
                self.logger.error("Empty voice command")
                if self.event_bus:
                    await self.event_bus.publish("voice.command.response", {
                        "success": False,
                        "error": "Empty command",
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
                return
                
            self.logger.info(f"Processing voice command: {command}")
            
            # Process the command (in a real implementation, this would parse and execute the command)
            # For now, just acknowledge receipt
            if self.event_bus:
                await self.event_bus.publish("voice.command.response", {
                    "success": True,
                    "command": command,
                    "processed": True,
                    "request_id": request_id,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error handling voice command: {str(e)}")
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
                
                await self.event_bus.publish("voice.command.response", error_data)

    async def _handle_voice_speak(self, data):
        """Handle voice speak event to synthesize speech.
        
        Args:
            data: Event data for voice speak request
        """
        try:
            if not isinstance(data, dict):
                self.logger.error("Invalid voice speak data: not a dictionary")
                return
                
            text = data.get('text', '')
            voice = data.get('voice', 'default')
            request_id = data.get('request_id', str(uuid.uuid4()))
            
            if not text:
                self.logger.error("Empty text for speech synthesis")
                if self.event_bus:
                    await self.event_bus.publish("voice.speak.response", {
                        "success": False,
                        "error": "Empty text",
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
                return
                
            self.logger.info(f"Synthesizing speech: {text[:30]}...")
            
            # Check if voice is enabled
            if not getattr(self, 'voice_enabled', False):
                self.logger.warning("Speech synthesis requested but voice is disabled")
                if self.event_bus:
                    await self.event_bus.publish("voice.speak.response", {
                        "success": False,
                        "error": "Voice is disabled",
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
                return
                
            try:
                import urllib.request
                import json as _json
                try:
                    from core.ollama_gateway import get_ollama_url
                    base = get_ollama_url()
                except ImportError:
                    base = "http://localhost:11434"
                req_body = _json.dumps({
                    "model": voice or getattr(self, "tts_model", "llama3"),
                    "prompt": f"Speak the following text: {text}",
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{base}/api/generate",
                    data=req_body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result_data = _json.loads(resp.read().decode("utf-8"))
                spoken = result_data.get("response", "").strip()
                if self.event_bus:
                    await self.event_bus.publish("voice.speak.response", {
                        "success": True,
                        "text": text,
                        "voice": voice,
                        "spoken_response": spoken,
                        "duration_ms": len(text) * 50,
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
            except Exception as tts_err:
                self.logger.warning(f"Voice synthesis unavailable: {tts_err}")
                if self.event_bus:
                    await self.event_bus.publish("voice.speak.response", {
                        "success": False,
                        "text": text,
                        "error": "Voice synthesis unavailable - no TTS backend configured",
                        "request_id": request_id,
                        "timestamp": datetime.now().isoformat()
                    })
                
        except Exception as e:
            self.logger.error(f"Error handling voice speak: {str(e)}")
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
                
                await self.event_bus.publish("voice.speak.response", error_data)

    async def _handle_speak_system_response(self, data):
        """Handle request to speak a system response.
        
        Args:
            data: Event data containing the system response to speak
        """
        try:
            if not isinstance(data, dict):
                self.logger.error("Invalid system response data: not a dictionary")
                return
                
            response = data.get('response', '')
            voice = data.get('voice', 'system')
            request_id = data.get('request_id', str(uuid.uuid4()))
            
            if not response:
                self.logger.error("Empty system response for speech synthesis")
                return
                
            self.logger.info(f"Speaking system response: {response[:30]}...")
            
            # Check if voice is enabled
            if not getattr(self, 'voice_enabled', False):
                self.logger.debug("System response speak requested but voice is disabled")
                return
                
            # Forward to the voice speak handler
            await self._handle_voice_speak({
                "text": response,
                "voice": voice,
                "request_id": request_id
            })
                
        except Exception as e:
            self.logger.error(f"Error handling system response speak: {str(e)}")
            self.logger.error(traceback.format_exc())

# Helper functions that will be migrated to MCPConnector class
class AIUtilityFunctions:
    """AI utility functions to be integrated with MCPConnector class"""
    
    async def discover_available_models(self, force_refresh=False):
        """Discover available AI models.
        
        Args:
            force_refresh: Force refreshing the model list
            
        Returns:
            List of available model names
        """
        self.logger.info("Discovering available AI models")
        
        # Implement discovery logic - for now just return some defaults
        models = ["llama2", "mistral", "codellama", "phi", "gemma"]
        
        # Store discovered models
        if not hasattr(self, 'available_models') or not isinstance(self.available_models, list):
            self.available_models = []
            
        for model in models:
            if model not in self.available_models:
                self.available_models.append(model)
                
        return self.available_models
    
    async def generate_chat_response(self, model, message, history=None):
        """Generate a chat response using the specified model.
        
        Args:
            model: Model name to use for generation
            message: User message
            history: Optional chat history
            
        Returns:
            Generated response text
        """
        self.logger.info(f"Generating chat response using model: {model}")
        
        # Wire to real Ollama for voice response generation
        try:
            import ollama
            ollama_client = ollama.Client(host=self.config.get("ollama_host", "http://localhost:11434") if hasattr(self, 'config') and self.config else "http://localhost:11434")
            
            # Generate response using Ollama
            response_obj = ollama_client.generate(
                model=model,
                prompt=f"User message: {message}\n\nGenerate a helpful, concise response:"
            )
            
            if response_obj and "response" in response_obj:
                response = response_obj["response"]
                self.logger.info("Generated response using Ollama")
                return response
            else:
                self.logger.warning("Ollama returned empty response")
                return "I'm having trouble generating a response right now. Please try again."
        except ImportError:
            self.logger.error("Ollama library not installed - cannot generate voice responses")
            return "Voice response generation unavailable - Ollama not installed"
        except Exception as e:
            self.logger.error(f"Error generating response with Ollama: {e}")
            return f"I encountered an error: {str(e)}"
    
    async def generate_completion(self, model, prompt):
        """Generate a completion using the specified model.
        
        Args:
            model: Model name to use for generation
            prompt: Text prompt for completion
            
        Returns:
            Generated completion text
        """
        self.logger.info(f"Generating completion using model: {model}")
        
        # Wire to real Ollama for completion generation
        try:
            import ollama
            ollama_client = ollama.Client(host=self.config.get("ollama_host", "http://localhost:11434") if hasattr(self, 'config') and self.config else "http://localhost:11434")
            
            # Generate completion using Ollama
            response_obj = ollama_client.generate(
                model=model,
                prompt=prompt
            )
            
            if response_obj and "response" in response_obj:
                response = response_obj["response"]
                self.logger.info("Generated completion using Ollama")
                return response
            else:
                self.logger.warning("Ollama returned empty completion")
                return "Completion generation failed. Please try again."
        except ImportError:
            self.logger.error("Ollama library not installed - cannot generate completions")
            return "Completion generation unavailable - Ollama not installed"
        except Exception as e:
            self.logger.error(f"Error generating completion with Ollama: {e}")
            return f"Completion error: {str(e)}"
        
    def _extract_code_from_response(self, response, language):
        """Extract code from AI response that might contain explanatory text.
        
        Args:
            response: The full response from the AI model
            language: The programming language to look for
            
        Returns:
            str: The extracted code or the full response if no code block is found
        """
        # Look for code blocks with markdown format: ```language ... ```
        import re
        pattern = f"```(?:{language})?\\n([\\s\\S]*?)\\n```"
        matches = re.findall(pattern, response)
        
        if matches:
            return matches[0].strip()
        
        # If no code block found, return the raw response
        return response.strip()
