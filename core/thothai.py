#!/usr/bin/env python3
"""
ThothAI for Kingdom AI
Handles AI functionalities including Ollama model integration
"""

import logging
import os
import json
import asyncio
import traceback
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional

from core.base_component import BaseComponent

# Try to import ollama client - we'll implement a fallback if it's not available
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    ollama = None

logger = logging.getLogger("KingdomAI.ThothAI")

class ThothAI(BaseComponent):
    """
    ThothAI implementation with Ollama integration
    
    This component provides:
    1. AI code generation capabilities
    2. Chat responses via Ollama models
    3. Auto-model pulling if models are not available
    4. Model parameter configuration
    """
    
    def __init__(self):
        super().__init__(name="ThothAI")
        self._initialized = False
        
        # Ollama configuration
        self.config = {
            'default_model': 'llama3',
            'fallback_model': 'llama2',
            'default_params': {
                'temperature': 0.7,
                'top_p': 0.9,
                'num_ctx': 4096
            },
            'auto_pull_models': True,
            'ollama_host': os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
        }
        
        # Model state tracking
        self.available_models = []
        self.current_model = None
        self.ollama_available = OLLAMA_AVAILABLE
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        logger.info("ThothAI initialized with Ollama integration")
        
    async def initialize(self, event_bus=None, config=None) -> bool:
        """Initialize the ThothAI with Ollama integration
        
        Args:
            event_bus: Optional EventBus instance to use for initialization
            config: Optional configuration to use for initialization
            
        Returns:
            bool: Success status
        """
        logger.info("ThothAI initializing...")
        
        # Set event_bus and config if provided (consistent with BaseComponent)
        if event_bus is not None:
            self.event_bus = event_bus
        if config is not None:
            self.config = config
        
        try:
            # Subscribe to events
            await self.subscribe_to_events()
            
            # Check Ollama availability
            if not self.ollama_available:
                logger.warning("Ollama package not available, attempting to install...")
                await self._install_ollama()
            
            # Configure Ollama client
            if self.ollama_available and ollama:
                # Set base URL for Ollama
                ollama.BASE_URL = self.config['ollama_host']
                
                # Check available models and pull if needed
                await self._check_models()
            else:
                logger.warning("Ollama not available - ThothAI will function with limited capabilities")
            
            self._initialized = True
            
            # Publish initialization status
            if hasattr(self, 'event_bus') and self.event_bus:
                await self.event_bus.publish("thoth.status", {
                    "status": "initialized",
                    "models_available": self.available_models,
                    "current_model": self.current_model,
                    "ollama_available": self.ollama_available
                })
                
            return True
            
        except Exception as e:
            logger.error(f"Error initializing ThothAI: {e}")
            logger.error(traceback.format_exc())
            self._initialized = False
            return False
            
    async def subscribe_to_events(self) -> bool:
        """Subscribe to all required events for ThothAI operation.
        
        This method sets up subscriptions for ThothAI to listen to relevant events
        from the event bus, including command requests and configuration changes.
        
        Returns:
            bool: True if subscriptions were successful, False otherwise
        """
        logger.info("Setting up ThothAI event subscriptions...")
        
        if not hasattr(self, 'event_bus') or self.event_bus is None:
            logger.error("Cannot subscribe to events: No event bus available")
            return False
            
        try:
            # Subscribe to command events - use simpler set of events initially 
            # to avoid missing handler errors while ensuring proper event bus connection
            success_sync = self.subscribe_sync("thoth.request", self.handle_request)
            success_async = self.subscribe_async("thoth.request_async", self.handle_request_async)
            
            if not (success_sync and success_async):
                logger.warning("Some ThothAI event subscriptions failed")
            
            logger.info("ThothAI event subscriptions set up successfully")
            return True
        except Exception as e:
            logger.error(f"Error setting up ThothAI event subscriptions: {e}")
            logger.error(traceback.format_exc())
            return False
            
    def handle_request(self, data):
        """Handle synchronous ThothAI requests.
        
        Args:
            data: Request data including command and parameters
        """
        logger.info(f"Received ThothAI request: {data}")
        try:
            if isinstance(data, dict) and 'command' in data:
                command = data['command']
                if command == 'get_models':
                    return {'status': 'success', 'models': self.available_models}
                elif command == 'get_status':
                    return {'status': 'success', 'initialized': self._initialized, 'model': self.current_model}
                else:
                    logger.warning(f"Unknown command: {command}")
                    return {'status': 'error', 'message': f'Unknown command: {command}'}
            else:
                logger.warning("Invalid request format")
                return {'status': 'error', 'message': 'Invalid request format'}
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return {'status': 'error', 'message': str(e)}
            
    async def handle_request_async(self, data):
        """Handle asynchronous ThothAI requests.
        
        Args:
            data: Request data including command and parameters
        """
        logger.info(f"Received async ThothAI request: {data}")
        try:
            if isinstance(data, dict) and 'command' in data:
                command = data['command']
                if command == 'generate':
                    prompt = data.get('prompt', '')
                    model = data.get('model', self.config.get('default_model', 'llama3'))
                    
                    # Call real Ollama API
                    ollama_url = f"{self.config['ollama_host']}/api/generate"
                    ollama_data = {
                        "model": model,
                        "prompt": prompt,
                        "stream": False
                    }
                    
                    try:
                        json_data = json.dumps(ollama_data).encode('utf-8')
                        req = urllib.request.Request(ollama_url, data=json_data, headers={'Content-Type': 'application/json'})
                        
                        with urllib.request.urlopen(req, timeout=60) as response:
                            response_text = response.read().decode('utf-8')
                            response_data = json.loads(response_text)
                            
                            if 'response' in response_data:
                                return {'status': 'success', 'response': response_data['response']}
                            else:
                                logger.warning(f"Unexpected Ollama response format: {response_data}")
                                return {'status': 'error', 'message': 'Unexpected response format from Ollama'}
                    except urllib.error.URLError as e:
                        error_msg = f"Ollama API unavailable: {str(e)}. Ensure Ollama is running at {self.config['ollama_host']}"
                        logger.warning(error_msg)
                        return {'status': 'error', 'message': f"AI processing unavailable — ensure Ollama is running. Error: {error_msg}"}
                    except Exception as e:
                        error_msg = f"Error calling Ollama API: {str(e)}"
                        logger.error(error_msg)
                        return {'status': 'error', 'message': f"AI processing unavailable — ensure Ollama is running. Error: {error_msg}"}
                else:
                    logger.warning(f"Unknown async command: {command}")
                    return {'status': 'error', 'message': f'Unknown async command: {command}'}
            else:
                logger.warning("Invalid async request format")
                return {'status': 'error', 'message': 'Invalid async request format'}
        except Exception as e:
            logger.error(f"Error handling async request: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _install_ollama(self) -> bool:
        """Attempt to install Ollama package in a secure manner
        
        Returns:
            bool: True if installation successful, False otherwise
        """
        try:
            # Try to install using pip in a secure manner
            import subprocess
            
            logger.info("Installing ollama package...")
            
            # Security measures:  # noqa: B404, B603 - Subprocess is required for pip installation as per Kingdom AI Global Rules
            # 1. Use absolute path to python executable (from sys.executable)
            # 2. Use a list of arguments rather than shell=True
            # 3. No user-supplied input in the command
            # 4. Timeout to prevent hanging
            # 5. Capture output for logging only
            
            # Safe executable paths
            python_executable = sys.executable
            pip_package = "ollama"
            
            # Execute pip install with timeout
            result = subprocess.run(
                [python_executable, "-m", "pip", "install", pip_package],
                capture_output=True,
                text=True,
                timeout=60,  # 1 minute timeout
                check=False  # Don't raise exception on non-zero return code
            )
            
            if result.returncode == 0:
                logger.info("Successfully installed ollama package")
                # Reimport ollama
                try:
                    import importlib
                    # Use importlib to safely reload the module
                    if "ollama" in sys.modules:
                        importlib.reload(sys.modules["ollama"])
                        ollama_module = sys.modules["ollama"]
                    else:
                        spec = importlib.util.find_spec("ollama")
                        if spec is not None:
                            ollama_module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(ollama_module)
                            sys.modules["ollama"] = ollama_module
                        else:
                            logger.error("Ollama module spec not found after installation")
                            return False
                            
                    # Update global state safely
                    self.ollama_available = True
                    return True
                except ImportError as e:
                    logger.error(f"Failed to import ollama after installation: {e}")
                    return False
            else:
                logger.error(f"Failed to install ollama package: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Timeout expired when installing ollama package")
            return False
        except Exception as e:
            logger.error(f"Error during ollama installation: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def _check_models(self):
        """Check available models and pull if needed"""
        if not self.ollama_available or not ollama:
            return False
            
        try:
            # Get list of available models
            logger.info("Checking available Ollama models...")
            for attempt in range(self.max_retries):
                try:
                    response = ollama.list()
                    if response and 'models' in response:
                        self.available_models = [model['name'] for model in response['models']]
                        logger.info(f"Available models: {self.available_models}")
                        break
                except Exception as e:
                    logger.warning(f"Attempt {attempt+1}/{self.max_retries} to list models failed: {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
            
            # Pull models if needed and auto-pull is enabled
            if self.config['auto_pull_models']:
                await self._ensure_model_available(self.config['default_model'])
                
            # Set current model
            if self.config['default_model'] in self.available_models:
                self.current_model = self.config['default_model']
            elif self.config['fallback_model'] in self.available_models:
                self.current_model = self.config['fallback_model']
                logger.warning(f"Default model not available, using fallback: {self.current_model}")
            elif self.available_models:
                self.current_model = self.available_models[0]
                logger.warning(f"Using available model: {self.current_model}")
            else:
                logger.error("No models available")
                return False
                
            logger.info(f"ThothAI using model: {self.current_model}")
            return True
            
        except Exception as e:
            logger.error(f"Error checking Ollama models: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def _ensure_model_available(self, model_name):
        """Ensure a specific model is available, pulling if needed"""
        if not self.ollama_available or not ollama:
            return False
            
        if model_name in self.available_models:
            logger.info(f"Model {model_name} is already available")
            return True
            
        # Model not available, attempt to pull
        logger.info(f"Model {model_name} not available, pulling...")
        try:
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"Pulling model {model_name} (attempt {attempt+1}/{self.max_retries})")
                    # This is a potentially long operation, so we don't await directly
                    # Instead, we'll use our own async wrapper
                    await self._async_pull_model(model_name)
                    
                    # Verify the model is now available
                    response = ollama.list()
                    if response and 'models' in response:
                        models = [model['name'] for model in response['models']]
                        if model_name in models:
                            self.available_models = models
                            logger.info(f"Successfully pulled model {model_name}")
                            return True
                            
                    logger.warning(f"Model {model_name} pull completed but not available in list")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
                        
                except Exception as e:
                    logger.warning(f"Attempt {attempt+1}/{self.max_retries} to pull model failed: {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
            
            logger.error(f"Failed to pull model {model_name} after {self.max_retries} attempts")
            return False
            
        except Exception as e:
            logger.error(f"Error ensuring model availability: {e}")
            return False
    
    async def _async_pull_model(self, model_name):
        """Asynchronous wrapper for Ollama's pull function with timeout handling"""
        def pull_task():
            try:
                # Use ollama pull function - this blocks
                # Set a 60 second timeout for initial connection
                start_time = time.time()
                logger.info(f"Starting pull of model {model_name}")
                ollama.pull(model_name, insecure=True)  # Add insecure=True to bypass SSL issues
                elapsed = time.time() - start_time
                logger.info(f"Successfully pulled model {model_name} in {elapsed:.2f} seconds")
                return True
            except Exception as e:
                logger.error(f"Error in pull task: {e}")
                logger.error(traceback.format_exc())
                return False
                
        # Run the blocking pull task in a thread pool with timeout
        loop = asyncio.get_event_loop()
        try:
            # Set a long 5-minute timeout since model downloads can take time
            pull_future = loop.run_in_executor(None, pull_task)
            result = await asyncio.wait_for(pull_future, timeout=300)  # 5 minute timeout
            return result
        except asyncio.TimeoutError:
            logger.error(f"Timeout when pulling model {model_name}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in async pull: {e}")
            logger.error(traceback.format_exc())
            return False
        
    async def generate_code(self, prompt: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate code using the Ollama model
        
        Args:
            prompt: The code generation prompt
            params: Optional parameters for the model
            
        Returns:
            Generated code as a string
        """
        if not self.initialized or not self.ollama_available:
            logger.error("Cannot generate code: ThothAI not properly initialized")
            return "Error: ThothAI not properly initialized"
            
        try:
            # Prepare model parameters
            model_params = self.config['default_params'].copy()
            if params:
                model_params.update(params)
                
            # Format the prompt for code generation
            formatted_prompt = f"Generate code for the following request. Only return the code, no explanations:\n\n{prompt}"
            
            # Make the API call
            for attempt in range(self.max_retries):
                try:
                    # Call Ollama API
                    response = ollama.generate(
                        model=self.current_model,
                        prompt=formatted_prompt,
                        options=model_params
                    )
                    
                    if response and 'response' in response:
                        return response['response'].strip()
                    else:
                        logger.warning(f"Unexpected response format: {response}")
                        
                except Exception as e:
                    logger.warning(f"Attempt {attempt+1}/{self.max_retries} failed: {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
            
            return "Error: Failed to generate code after multiple attempts"
            
        except Exception as e:
            logger.error(f"Error generating code: {e}")
            return f"Error generating code: {str(e)}"
    
    async def generate_response(self, prompt: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate a chat response using the Ollama model
        
        Args:
            prompt: The chat prompt
            params: Optional parameters for the model
            
        Returns:
            Generated response as a string
        """
        if not self.initialized or not self.ollama_available:
            logger.error("Cannot generate response: ThothAI not properly initialized")
            return "Error: ThothAI not properly initialized"
            
        try:
            # Prepare model parameters
            model_params = self.config['default_params'].copy()
            if params:
                model_params.update(params)
                
            # Make the API call
            for attempt in range(self.max_retries):
                try:
                    # Call Ollama API
                    response = ollama.chat(
                        model=self.current_model,
                        messages=[{"role": "user", "content": prompt}],
                        options=model_params
                    )
                    
                    if response and 'message' in response and 'content' in response['message']:
                        return response['message']['content'].strip()
                    else:
                        logger.warning(f"Unexpected response format: {response}")
                        
                except Exception as e:
                    logger.warning(f"Attempt {attempt+1}/{self.max_retries} failed: {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
            
            return "Error: Failed to generate response after multiple attempts"
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error generating response: {str(e)}"
    
    async def subscribe_to_events(self):
        """Subscribe to events from the event bus"""
        if hasattr(self, 'event_bus') and self.event_bus:
            logger.info("Subscribing to events...")
            self.event_bus.subscribe_sync('system.status', self.handle_system_status)
            self.event_bus.subscribe_sync('system.shutdown', self.cleanup)
            self.event_bus.subscribe_sync('system.health.check', self.handle_health_check)
            self.event_bus.subscribe_sync('system.metrics.analyze', self.handle_metrics_analysis)
            self.event_bus.subscribe_sync('portfolio.metrics.analyze', self.handle_portfolio_analysis)
            self.event_bus.subscribe_sync('code.generate', self.handle_code_generation)
            self.event_bus.subscribe_sync('code.repair', self.handle_code_repair)
            logger.info("Event subscriptions complete")
    
    def subscribe_to_events_sync(self):
        """Synchronous version of subscribe_to_events"""
        if hasattr(self, 'event_bus') and self.event_bus:
            logger.info("Subscribing to events (sync)...")
            self.event_bus.subscribe_sync('system.status', self.handle_system_status)
            self.event_bus.subscribe_sync('system.shutdown', self.cleanup)
            self.event_bus.subscribe_sync('system.health.check', self.handle_health_check)
            self.event_bus.subscribe_sync('system.metrics.analyze', self.handle_metrics_analysis)
            self.event_bus.subscribe_sync('portfolio.metrics.analyze', self.handle_portfolio_analysis)
            self.event_bus.subscribe_sync('code.generate', self.handle_code_generation)
            self.event_bus.subscribe_sync('code.repair', self.handle_code_repair)
            logger.info("Event subscriptions complete")
    
    async def handle_system_status(self, event_data=None):
        """Handle system status events"""
        logger.debug(f"Received system status: {event_data}")
        
        # Check if we need to reinitialize
        if event_data and 'status' in event_data:
            if event_data['status'] == 'reinitialize':
                logger.info("Reinitializing ThothAI due to system status event")
                await self.initialize()
                
    async def handle_health_check(self, event_data=None):
        """Handle system health check events"""
        logger.debug("Performing ThothAI health check")
        
        # Check Ollama status
        ollama_status = "available" if self.ollama_available else "unavailable"
        model_status = f"using {self.current_model}" if self.current_model else "no model selected"
        
        # Publish health status
        if hasattr(self, 'event_bus') and self.event_bus:
            await self.event_bus.publish("thoth.health", {
                "status": "healthy" if self.initialized and self.ollama_available else "degraded",
                "ollama": ollama_status,
                "model": model_status,
                "available_models": self.available_models
            })
    
    async def handle_metrics_analysis(self, event_data=None):
        """Handle system metrics analysis requests"""
        if not event_data or not isinstance(event_data, dict):
            logger.warning("Invalid metrics analysis request")
            return
            
        logger.info(f"Analyzing system metrics: {event_data}")
        
        # Generate analysis using AI model
        metrics_prompt = f"Analyze the following system metrics and provide insights: {json.dumps(event_data)}"
        analysis = await self.generate_response(metrics_prompt)
        
        # Publish analysis
        if hasattr(self, 'event_bus') and self.event_bus:
            await self.event_bus.publish("thoth.analysis", {
                "type": "system_metrics",
                "request_id": event_data.get("request_id"),
                "analysis": analysis
            })
    
    async def handle_portfolio_analysis(self, event_data=None):
        """Handle portfolio metrics analysis requests"""
        if not event_data or not isinstance(event_data, dict):
            logger.warning("Invalid portfolio analysis request")
            return
            
        logger.info(f"Analyzing portfolio metrics: {event_data}")
        
        # Generate analysis using AI model
        portfolio_prompt = f"Analyze the following portfolio data and provide trading insights: {json.dumps(event_data)}"
        analysis = await self.generate_response(portfolio_prompt)
        
        # Publish analysis
        if hasattr(self, 'event_bus') and self.event_bus:
            await self.event_bus.publish("thoth.analysis", {
                "type": "portfolio",
                "request_id": event_data.get("request_id"),
                "analysis": analysis
            })
    
    async def handle_code_generation(self, event_data=None):
        """Handle code generation requests"""
        if not event_data or not isinstance(event_data, dict) or 'prompt' not in event_data:
            logger.warning("Invalid code generation request")
            return
            
        logger.info(f"Generating code for prompt: {event_data['prompt'][:50]}...")
        
        # Generate code
        code = await self.generate_code(event_data['prompt'])
        
        # Publish generated code
        if hasattr(self, 'event_bus') and self.event_bus:
            await self.event_bus.publish("thoth.code", {
                "type": "generated",
                "request_id": event_data.get("request_id"),
                "code": code
            })
    
    async def handle_code_repair(self, event_data=None):
        """Handle code repair requests"""
        if not event_data or not isinstance(event_data, dict) or 'code' not in event_data:
            logger.warning("Invalid code repair request")
            return
            
        logger.info("Repairing code...")
        
        # Prepare repair prompt
        error = event_data.get('error', 'Fix any issues in this code')
        repair_prompt = f"Fix the following code:\n```\n{event_data['code']}\n```\nError: {error}\n\nProvide only the fixed code."
        
        # Generate repaired code
        repaired_code = await self.generate_code(repair_prompt)
        
        # Publish repaired code
        if hasattr(self, 'event_bus') and self.event_bus:
            await self.event_bus.publish("thoth.code", {
                "type": "repaired",
                "request_id": event_data.get("request_id"),
                "code": repaired_code
            })
        
    async def cleanup(self, event_data=None) -> bool:
        """Clean up resources
        
        Args:
            event_data: Optional event data
            
        Returns:
            bool: True if cleanup successful, False otherwise
        """
        logger.info("Cleaning up ThothAI...")
        
        try:
            self.initialized = False
            
            # Publish cleanup status
            if hasattr(self, 'event_bus') and self.event_bus:
                await self.event_bus.publish("thoth.status", {
                    "status": "shutdown",
                    "timestamp": str(datetime.now()),
                    "success": True
                })
            
            return True
        except Exception as e:
            logger.error(f"Error during ThothAI cleanup: {e}")
            logger.error(traceback.format_exc())
            return False

import sys
from datetime import datetime
