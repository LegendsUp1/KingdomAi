"""
Enhanced Ollama Brain with VL-JEPA Integration
===============================================

Upgrades the existing Ollama brain with VL-JEPA's continuous embedding
prediction for improved performance and efficiency across all subsystems.
"""

import asyncio
import logging
import aiohttp
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

# Safe PyTorch import with DLL error handling
torch = None
torch_available = False
try:
    import torch
    # Test if PyTorch can be used without DLL errors
    _ = torch.tensor([1, 2, 3])
    torch_available = True
except Exception as torch_error:
    logging.warning(f"PyTorch import failed: {torch_error}")
    logging.warning("VL-JEPA brain will be disabled due to PyTorch DLL issues")

# Only import VL-JEPA if PyTorch is available
if torch_available:
    try:
        from core.vl_jepa.integration import VLJEPAIntegration, VLJEPAIntegrationConfig
        VL_JEPA_AVAILABLE = True
    except ImportError:
        VL_JEPA_AVAILABLE = False
        logging.warning("VL-JEPA integration not available")
else:
    VL_JEPA_AVAILABLE = False
    # Create dummy classes for type hints
    class VLJEPAIntegration:
        pass
    class VLJEPAIntegrationConfig:
        pass

logger = logging.getLogger(__name__)


class OllamaVLJEPABrain:
    """
    Enhanced Ollama brain with VL-JEPA integration.
    Provides 50% parameter reduction and 2.85x selective decoding efficiency.
    """
    
    def __init__(self, event_bus=None, redis_client=None):
        """Initialize enhanced Ollama brain with VL-JEPA"""
        self.event_bus = event_bus
        self.redis_client = redis_client
        
        # Ollama configuration
        try:
            from core.ollama_gateway import get_ollama_url
            self.ollama_base_url = get_ollama_url() + "/api"
        except ImportError:
            self.ollama_base_url = "http://localhost:11434/api"
        self.current_model = "llama3.1"
        
        # Initialize VL-JEPA integration
        vl_jepa_config = VLJEPAIntegrationConfig(
            enable_for_trading=True,
            enable_for_mining=True,
            enable_for_blockchain=True,
            enable_for_wallet=True,
            enable_for_thoth=True,
            enable_for_codegen=True,
            enable_for_vr=True,
            enable_selective_decode=True,
            cache_embeddings=True,
            learning_enabled=True
        )
        
        self.vl_jepa = VLJEPAIntegration(
            event_bus=event_bus,
            config=vl_jepa_config
        )
        
        # Performance tracking
        self.performance_stats = {
            'total_requests': 0,
            'vl_jepa_requests': 0,
            'ollama_fallbacks': 0,
            'average_response_time': 0.0,
            'embedding_cache_hits': 0
        }
        
        # Context management
        self.conversation_context = []
        self.max_context_length = 10
        
        logger.info("Ollama VL-JEPA Brain initialized")
    
    async def initialize(self):
        """Initialize the enhanced brain"""
        try:
            # Initialize VL-JEPA
            vl_jepa_initialized = await self.vl_jepa.initialize()
            
            # Check Ollama availability
            ollama_available = await self._check_ollama()
            
            # Set up event subscriptions
            if self.event_bus:
                await self._setup_event_subscriptions()
            
            # Log initialization status
            logger.info(f"VL-JEPA initialized: {vl_jepa_initialized}")
            logger.info(f"Ollama available: {ollama_available}")
            
            # Publish initialization event
            if self.event_bus:
                self.event_bus.publish('ollama_vl_jepa.initialized', {
                    'vl_jepa': vl_jepa_initialized,
                    'ollama': ollama_available,
                    'timestamp': datetime.now().isoformat()
                })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Ollama VL-JEPA Brain: {e}")
            return False
    
    async def _check_ollama(self) -> bool:
        """Check if Ollama is available"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_base_url}/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m['name'] for m in data.get('models', [])]
                        logger.info(f"Ollama available with models: {models}")
                        return True
            return False
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False
    
    async def _setup_event_subscriptions(self):
        """Set up event bus subscriptions"""
        # SOTA 2026 FIX: Do NOT subscribe to ai.request — ThothAI is the single handler.
        # Duplicate subscriptions caused 4-5x GPU contention on every user query.
        # VL-JEPA brain is available via direct method calls when ThothAI needs embeddings.
        self.event_bus.subscribe('ai.model_update', self._handle_model_update)
        
        # Learning events
        self.event_bus.subscribe('learning.metrics', self._handle_learning_metrics)
        self.event_bus.subscribe('learning.readiness', self._handle_learning_readiness)
        
        # Tab-specific enhanced processing
        self.event_bus.subscribe('trading.ai_analyze', self.analyze_trading)
        self.event_bus.subscribe('mining.ai_optimize', self.optimize_mining)
        self.event_bus.subscribe('blockchain.ai_analyze', self.analyze_blockchain)
        self.event_bus.subscribe('wallet.ai_assess', self.assess_wallet)
        self.event_bus.subscribe('code.ai_generate', self.generate_code)
        self.event_bus.subscribe('vr.ai_process', self.process_vr)
        
        logger.info("Ollama VL-JEPA event subscriptions established")
    
    async def process_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process AI request with VL-JEPA enhancement.
        Uses continuous embedding prediction for efficiency.
        """
        try:
            start_time = asyncio.get_event_loop().time()
            self.performance_stats['total_requests'] += 1
            
            # Extract request details
            prompt = data.get('prompt') or data.get('message', '')
            require_text = data.get('require_text', True)
            use_vl_jepa = data.get('use_vl_jepa', True)
            
            # Add to conversation context
            self._update_context({'role': 'user', 'content': prompt})
            
            response = None
            embedding = None
            
            if use_vl_jepa:
                # Use VL-JEPA for efficient processing
                try:
                    # Process through VL-JEPA
                    embedding, response_text = await self.vl_jepa.process_multimodal(
                        text=prompt,
                        image=data.get('image'),
                        context={
                            'conversation': self.conversation_context,
                            'metadata': data.get('metadata', {})
                        }
                    )
                    
                    if require_text and response_text:
                        response = response_text
                    else:
                        response = embedding
                    
                    self.performance_stats['vl_jepa_requests'] += 1
                    
                except Exception as e:
                    logger.warning(f"VL-JEPA processing failed, falling back to Ollama: {e}")
                    use_vl_jepa = False
            
            # Fallback to standard Ollama if needed
            if not use_vl_jepa or response is None:
                response = await self._process_with_ollama(prompt)
                self.performance_stats['ollama_fallbacks'] += 1
            
            # Update context with response
            self._update_context({'role': 'assistant', 'content': response if isinstance(response, str) else 'embedding'})
            
            # Calculate performance metrics
            elapsed = asyncio.get_event_loop().time() - start_time
            self._update_performance_stats(elapsed)
            
            # Prepare result
            result = {
                'request': prompt,
                'response': response,
                'model': self.current_model,
                'processing_time': elapsed,
                'method': 'vl_jepa' if use_vl_jepa else 'ollama'
            }
            
            if embedding is not None:
                result['embedding'] = embedding.tolist() if isinstance(embedding, torch.Tensor) else embedding
            
            # Publish response event
            if self.event_bus:
                self.event_bus.publish('ai.response', result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return {
                'error': str(e),
                'request': data.get('prompt', ''),
                'response': f"Error processing request: {str(e)}"
            }
    
    async def _process_with_ollama(self, prompt: str) -> str:
        """Process request with standard Ollama"""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'model': self.current_model,
                    'prompt': prompt,
                    'stream': False
                }
                
                async with session.post(
                    f"{self.ollama_base_url}/generate",
                    json=data,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('response', 'No response generated')
                    else:
                        return f"Ollama error: {response.status}"
                        
        except Exception as e:
            logger.error(f"Ollama processing error: {e}")
            return f"Processing error: {str(e)}"
    
    async def analyze_trading(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trading data with VL-JEPA"""
        embedding, analysis = await self.vl_jepa.process_multimodal(
            text=f"Analyze trading data for {data.get('symbol', 'asset')}",
            context={'type': 'trading_analysis', **data}
        )
        return {'analysis': analysis, 'embedding': embedding}
    
    async def optimize_mining(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize mining with VL-JEPA"""
        embedding, recommendation = await self.vl_jepa.process_multimodal(
            text="Optimize mining configuration",
            context={'type': 'mining_optimization', **data}
        )
        return {'recommendation': recommendation, 'embedding': embedding}
    
    async def analyze_blockchain(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze blockchain with VL-JEPA"""
        embedding, analysis = await self.vl_jepa.process_multimodal(
            text=f"Analyze {data.get('network', 'blockchain')} network",
            context={'type': 'blockchain_analysis', **data}
        )
        return {'analysis': analysis, 'embedding': embedding}
    
    async def assess_wallet(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess wallet with VL-JEPA"""
        embedding, assessment = await self.vl_jepa.process_multimodal(
            text="Assess wallet security and risk",
            context={'type': 'wallet_assessment', **data}
        )
        return {'assessment': assessment, 'embedding': embedding}
    
    async def generate_code(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code with VL-JEPA"""
        embedding, code = await self.vl_jepa.process_multimodal(
            text=data.get('prompt', 'Generate code'),
            context={'type': 'code_generation', **data}
        )
        return {'code': code, 'language': data.get('language', 'python')}
    
    async def process_vr(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process VR data with VL-JEPA"""
        embedding, understanding = await self.vl_jepa.process_multimodal(
            text=data.get('command', 'Process VR input'),
            image=data.get('frame'),
            context={'type': 'vr_processing', **data}
        )
        return {'understanding': understanding, 'embedding': embedding}
    
    def _update_context(self, message: Dict[str, str]):
        """Update conversation context"""
        self.conversation_context.append(message)
        if len(self.conversation_context) > self.max_context_length:
            self.conversation_context = self.conversation_context[-self.max_context_length:]
    
    def _update_performance_stats(self, elapsed: float):
        """Update performance statistics"""
        n = self.performance_stats['total_requests']
        avg = self.performance_stats['average_response_time']
        self.performance_stats['average_response_time'] = (avg * (n - 1) + elapsed) / n
    
    async def _handle_model_update(self, data: Dict[str, Any]):
        """Handle model update request"""
        new_model = data.get('model')
        if new_model:
            self.current_model = new_model
            logger.info(f"Updated model to: {new_model}")
    
    async def _handle_learning_metrics(self, data: Dict[str, Any]):
        """Handle learning metrics update"""
        await self.vl_jepa.vl_jepa.learn_from_context({
            'type': 'learning_metrics',
            'metrics': data
        })
    
    async def _handle_learning_readiness(self, data: Dict[str, Any]):
        """Handle learning readiness update"""
        state = data.get('state')
        if state == 'READY':
            logger.info("System learning ready - VL-JEPA optimized")
    
    def get_status(self) -> Dict[str, Any]:
        """Get brain status"""
        return {
            'ollama_model': self.current_model,
            'performance_stats': self.performance_stats,
            'vl_jepa_status': self.vl_jepa.get_status(),
            'context_size': len(self.conversation_context)
        }
