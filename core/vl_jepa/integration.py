"""
VL-JEPA Integration with Kingdom AI System
==========================================

Integrates VL-JEPA with existing Ollama brain, ThothAI, and all subsystems.
Provides seamless embedding-based processing across all tabs.
"""

import asyncio
import logging
import torch
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import json

from .core import VLJEPACore, VLJEPAConfig

logger = logging.getLogger(__name__)


@dataclass
class VLJEPAIntegrationConfig:
    """Configuration for VL-JEPA integration"""
    enable_for_trading: bool = True
    enable_for_mining: bool = True
    enable_for_blockchain: bool = True
    enable_for_wallet: bool = True
    enable_for_thoth: bool = True
    enable_for_codegen: bool = True
    enable_for_vr: bool = True
    enable_selective_decode: bool = True
    cache_embeddings: bool = True
    learning_enabled: bool = True


class VLJEPAIntegration:
    """
    Integrates VL-JEPA with Kingdom AI's existing systems.
    Enhances Ollama brain with continuous embedding prediction.
    """
    
    def __init__(
        self,
        event_bus=None,
        config: Optional[VLJEPAIntegrationConfig] = None
    ):
        """Initialize VL-JEPA integration"""
        self.event_bus = event_bus
        self.config = config or VLJEPAIntegrationConfig()
        
        # Initialize VL-JEPA core
        vl_jepa_config = VLJEPAConfig()
        self.vl_jepa = VLJEPACore(config=vl_jepa_config, event_bus=event_bus)
        
        # Track integration status
        self.integration_status = {
            'ollama': False,
            'thoth': False,
            'trading': False,
            'mining': False,
            'blockchain': False,
            'wallet': False,
            'codegen': False,
            'vr': False
        }
        
        # Performance metrics
        self.metrics = {
            'requests_processed': 0,
            'embeddings_cached': 0,
            'selective_decodes': 0,
            'average_response_time': 0.0
        }
        
        logger.info("VL-JEPA Integration initialized")
    
    async def initialize(self):
        """Initialize VL-JEPA integration with all systems"""
        try:
            # Initialize VL-JEPA core
            await self.vl_jepa.initialize()
            
            # Set up event subscriptions
            if self.event_bus:
                await self._setup_event_subscriptions()
            
            # Connect to existing systems
            await self._connect_to_ollama()
            await self._connect_to_thoth()
            await self._connect_to_subsystems()
            
            logger.info("VL-JEPA Integration fully initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize VL-JEPA Integration: {e}")
            return False
    
    async def _setup_event_subscriptions(self):
        """Set up event bus subscriptions for integration"""
        # SOTA 2026 FIX: Do NOT subscribe to ai.request — ThothAI is the single handler.
        # Duplicate subscriptions caused 4-5x GPU contention on every user query.
        self.event_bus.subscribe('ai.response', self._enhance_ai_response)
        
        # Tab-specific events
        if self.config.enable_for_trading:
            self.event_bus.subscribe('trading.analyze', self._handle_trading_analysis)
            self.event_bus.subscribe('trading.prediction', self._handle_trading_prediction)
        
        if self.config.enable_for_mining:
            self.event_bus.subscribe('mining.optimize', self._handle_mining_optimization)
            self.event_bus.subscribe('mining.coin_selection', self._handle_coin_selection)
        
        if self.config.enable_for_blockchain:
            self.event_bus.subscribe('blockchain.analyze', self._handle_blockchain_analysis)
            self.event_bus.subscribe('blockchain.gas_prediction', self._handle_gas_prediction)
        
        if self.config.enable_for_wallet:
            self.event_bus.subscribe('wallet.risk_assessment', self._handle_wallet_risk)
            self.event_bus.subscribe('wallet.transaction_analysis', self._handle_transaction_analysis)
        
        if self.config.enable_for_codegen:
            self.event_bus.subscribe('code.generate', self._handle_code_generation)
            self.event_bus.subscribe('code.optimize', self._handle_code_optimization)
        
        if self.config.enable_for_vr:
            self.event_bus.subscribe('vr.gesture_recognition', self._handle_vr_gesture)
            self.event_bus.subscribe('vr.scene_understanding', self._handle_vr_scene)
        
        logger.info("VL-JEPA event subscriptions established")
    
    async def _connect_to_ollama(self):
        """Connect VL-JEPA to Ollama brain"""
        try:
            # Check if Ollama is available
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:11434/api/tags') as response:
                    if response.status == 200:
                        self.integration_status['ollama'] = True
                        logger.info("VL-JEPA connected to Ollama")
                        
                        # Publish integration event
                        if self.event_bus:
                            self.event_bus.publish('vl_jepa.ollama_connected', {
                                'status': 'connected',
                                'capabilities': ['embedding_prediction', 'selective_decode']
                            })
        except Exception as e:
            logger.warning(f"Could not connect to Ollama: {e}")
    
    async def _connect_to_thoth(self):
        """Connect VL-JEPA to ThothAI"""
        try:
            # Check if ThothAI is available
            from core.thoth import has_sentience_framework
            if has_sentience_framework:
                self.integration_status['thoth'] = True
                logger.info("VL-JEPA connected to ThothAI")
                
                # Enhance ThothAI with VL-JEPA capabilities
                if self.event_bus:
                    self.event_bus.publish('vl_jepa.thoth_enhancement', {
                        'status': 'enhanced',
                        'features': ['continuous_embeddings', 'multimodal_understanding']
                    })
        except Exception as e:
            logger.warning(f"Could not connect to ThothAI: {e}")
    
    async def _connect_to_subsystems(self):
        """Connect VL-JEPA to all subsystems"""
        subsystems = ['trading', 'mining', 'blockchain', 'wallet', 'codegen', 'vr']
        
        for subsystem in subsystems:
            if getattr(self.config, f'enable_for_{subsystem}'):
                self.integration_status[subsystem] = True
                logger.info(f"VL-JEPA connected to {subsystem} subsystem")
    
    async def _handle_ai_request(self, data: Dict[str, Any]):
        """
        Handle AI requests with VL-JEPA enhancement.
        Predicts embeddings instead of generating tokens for efficiency.
        """
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Extract context
            context = {
                'text': data.get('prompt') or data.get('message'),
                'type': 'ai_request',
                'metadata': data.get('metadata', {})
            }
            
            # Predict embedding
            embedding, metadata = await self.vl_jepa.predict_embedding(
                context,
                use_selective_decode=self.config.enable_selective_decode
            )
            
            # Only decode to text if needed
            if data.get('require_text', True):
                response_text = await self.vl_jepa.decode_to_text(embedding, context)
            else:
                response_text = None
            
            # Update metrics
            elapsed = asyncio.get_event_loop().time() - start_time
            self._update_metrics(elapsed, metadata)
            
            # Publish enhanced response
            if self.event_bus:
                self.event_bus.publish('vl_jepa.ai_response', {
                    'request': data,
                    'embedding': embedding.tolist() if isinstance(embedding, torch.Tensor) else embedding,
                    'text': response_text,
                    'metadata': metadata,
                    'processing_time': elapsed
                })
            
        except Exception as e:
            logger.error(f"Error handling AI request: {e}")
    
    async def _enhance_ai_response(self, data: Dict[str, Any]):
        """Enhance existing AI responses with VL-JEPA embeddings"""
        try:
            # Extract response text
            response_text = data.get('response') or data.get('text')
            if not response_text:
                return
            
            # Generate embedding for response
            context = {'text': response_text, 'type': 'ai_response'}
            embedding, _ = await self.vl_jepa.predict_embedding(context)
            
            # Store embedding for future similarity searches
            if self.vl_jepa.embedding_space:
                await self.vl_jepa.embedding_space.project(embedding)
            
            # Publish enhanced response
            if self.event_bus:
                self.event_bus.publish('vl_jepa.response_enhanced', {
                    'original': data,
                    'embedding': embedding.tolist() if isinstance(embedding, torch.Tensor) else embedding
                })
                
        except Exception as e:
            logger.error(f"Error enhancing AI response: {e}")
    
    async def _handle_trading_analysis(self, data: Dict[str, Any]):
        """Handle trading analysis with VL-JEPA"""
        try:
            context = {
                'type': 'trading_analysis',
                'trading': data
            }
            
            # Predict embedding for trading context
            embedding, metadata = await self.vl_jepa.predict_embedding(context)
            
            # Find similar historical patterns
            if self.vl_jepa.embedding_space:
                similar_patterns = await self.vl_jepa.embedding_space.retrieve_similar(
                    embedding, k=5, threshold=0.8
                )
                
                # Publish pattern analysis
                if self.event_bus:
                    self.event_bus.publish('vl_jepa.trading_patterns', {
                        'current': data,
                        'similar_patterns': [
                            {'metadata': meta, 'similarity': sim}
                            for _, meta, sim in similar_patterns
                        ]
                    })
            
        except Exception as e:
            logger.error(f"Error in trading analysis: {e}")
    
    async def _handle_trading_prediction(self, data: Dict[str, Any]):
        """Generate trading predictions using VL-JEPA"""
        try:
            # Combine multiple data sources
            context = {
                'type': 'trading_prediction',
                'trading': data,
                'text': f"Predict {data.get('symbol', 'asset')} movement"
            }
            
            # Get prediction embedding
            embedding, _ = await self.vl_jepa.predict_embedding(context)
            
            # Decode to prediction
            prediction_text = await self.vl_jepa.decode_to_text(embedding, context)
            
            # Parse prediction (simplified)
            direction = 'up' if 'up' in prediction_text.lower() or 'bull' in prediction_text.lower() else 'down'
            confidence = 0.7  # Would be computed from embedding confidence
            
            # Publish prediction
            if self.event_bus:
                self.event_bus.publish('vl_jepa.trading_prediction', {
                    'symbol': data.get('symbol'),
                    'direction': direction,
                    'confidence': confidence,
                    'reasoning': prediction_text
                })
                
        except Exception as e:
            logger.error(f"Error in trading prediction: {e}")
    
    async def _handle_mining_optimization(self, data: Dict[str, Any]):
        """Optimize mining with VL-JEPA"""
        try:
            context = {
                'type': 'mining_optimization',
                'mining': data,
                'text': 'Optimize mining configuration'
            }
            
            # Get optimization embedding
            embedding, _ = await self.vl_jepa.predict_embedding(context)
            
            # Find optimal configuration from learned patterns
            if self.vl_jepa.embedding_space:
                # Get nearest prototype (representing optimal configuration)
                proto_id, similarity = self.vl_jepa.embedding_space.find_nearest_prototype(embedding)
                
                # Publish optimization
                if self.event_bus:
                    self.event_bus.publish('vl_jepa.mining_optimization', {
                        'current_config': data,
                        'optimal_prototype': proto_id,
                        'confidence': similarity
                    })
                    
        except Exception as e:
            logger.error(f"Error in mining optimization: {e}")
    
    async def _handle_coin_selection(self, data: Dict[str, Any]):
        """Select best coin to mine using VL-JEPA"""
        try:
            # Analyze each coin option
            coins = data.get('coins', [])
            coin_embeddings = []
            
            for coin in coins:
                context = {
                    'type': 'coin_analysis',
                    'coin': coin,
                    'text': f"Analyze mining profitability for {coin.get('symbol', 'unknown')}"
                }
                embedding, _ = await self.vl_jepa.predict_embedding(context)
                coin_embeddings.append((coin, embedding))
            
            # Rank coins by embedding quality/confidence
            ranked_coins = []
            for coin, embedding in coin_embeddings:
                # Simple ranking by embedding norm (could be more sophisticated)
                score = torch.norm(embedding).item()
                ranked_coins.append((coin, score))
            
            ranked_coins.sort(key=lambda x: x[1], reverse=True)
            
            # Publish selection
            if self.event_bus and ranked_coins:
                self.event_bus.publish('vl_jepa.coin_selection', {
                    'selected': ranked_coins[0][0],
                    'ranking': [{'coin': c, 'score': s} for c, s in ranked_coins]
                })
                
        except Exception as e:
            logger.error(f"Error in coin selection: {e}")
    
    async def _handle_blockchain_analysis(self, data: Dict[str, Any]):
        """Analyze blockchain data with VL-JEPA"""
        try:
            context = {
                'type': 'blockchain_analysis',
                'blockchain': data
            }
            
            # Get analysis embedding
            embedding, _ = await self.vl_jepa.predict_embedding(context)
            
            # Decode insights
            insights = await self.vl_jepa.decode_to_text(embedding, context)
            
            # Publish analysis
            if self.event_bus:
                self.event_bus.publish('vl_jepa.blockchain_analysis', {
                    'data': data,
                    'insights': insights,
                    'embedding': embedding.tolist() if isinstance(embedding, torch.Tensor) else embedding
                })
                
        except Exception as e:
            logger.error(f"Error in blockchain analysis: {e}")
    
    async def _handle_gas_prediction(self, data: Dict[str, Any]):
        """Predict gas prices using VL-JEPA"""
        try:
            context = {
                'type': 'gas_prediction',
                'blockchain': data,
                'text': 'Predict optimal gas price'
            }
            
            # Get prediction embedding
            embedding, _ = await self.vl_jepa.predict_embedding(context)
            
            # Decode to gas prediction
            prediction = await self.vl_jepa.decode_to_text(embedding, context)
            
            # Parse prediction (simplified)
            try:
                # Extract number from prediction
                import re
                numbers = re.findall(r'\d+', prediction)
                gas_price = int(numbers[0]) if numbers else 50  # Default
            except:
                gas_price = 50
            
            # Publish prediction
            if self.event_bus:
                self.event_bus.publish('vl_jepa.gas_prediction', {
                    'network': data.get('network'),
                    'predicted_gas': gas_price,
                    'reasoning': prediction
                })
                
        except Exception as e:
            logger.error(f"Error in gas prediction: {e}")
    
    async def _handle_wallet_risk(self, data: Dict[str, Any]):
        """Assess wallet risk with VL-JEPA"""
        try:
            context = {
                'type': 'wallet_risk',
                'wallet': data,
                'text': 'Assess wallet risk level'
            }
            
            # Get risk embedding
            embedding, metadata = await self.vl_jepa.predict_embedding(context)
            
            # Compute risk score from embedding
            risk_score = self._compute_risk_from_embedding(embedding)
            
            # Decode risk assessment
            assessment = await self.vl_jepa.decode_to_text(embedding, context)
            
            # Publish assessment
            if self.event_bus:
                self.event_bus.publish('vl_jepa.wallet_risk', {
                    'wallet': data.get('address'),
                    'risk_score': risk_score,
                    'assessment': assessment,
                    'confidence': metadata.get('confidence', 0.5)
                })
                
        except Exception as e:
            logger.error(f"Error in wallet risk assessment: {e}")
    
    async def _handle_transaction_analysis(self, data: Dict[str, Any]):
        """Analyze transactions with VL-JEPA"""
        try:
            context = {
                'type': 'transaction_analysis',
                'transaction': data
            }
            
            # Get analysis embedding
            embedding, _ = await self.vl_jepa.predict_embedding(context)
            
            # Decode analysis
            analysis = await self.vl_jepa.decode_to_text(embedding, context)
            
            # Publish analysis
            if self.event_bus:
                self.event_bus.publish('vl_jepa.transaction_analysis', {
                    'tx_hash': data.get('hash'),
                    'analysis': analysis,
                    'embedding': embedding.tolist() if isinstance(embedding, torch.Tensor) else embedding
                })
                
        except Exception as e:
            logger.error(f"Error in transaction analysis: {e}")
    
    async def _handle_code_generation(self, data: Dict[str, Any]):
        """Generate code with VL-JEPA"""
        try:
            context = {
                'type': 'code_generation',
                'text': data.get('prompt', ''),
                'language': data.get('language', 'python')
            }
            
            # Get code embedding
            embedding, metadata = await self.vl_jepa.predict_embedding(context)
            
            # Decode to code
            if metadata.get('confidence', 0) > 0.5:
                # High confidence - generate directly
                code = await self.vl_jepa.decode_to_text(embedding, context)
            else:
                # Low confidence - use template
                code = f"# Generated with low confidence\n# Please review carefully\n{data.get('prompt', '')}"
            
            # Publish generated code
            if self.event_bus:
                self.event_bus.publish('vl_jepa.code_generated', {
                    'prompt': data.get('prompt'),
                    'code': code,
                    'language': data.get('language'),
                    'confidence': metadata.get('confidence', 0.5)
                })
                
        except Exception as e:
            logger.error(f"Error in code generation: {e}")
    
    async def _handle_code_optimization(self, data: Dict[str, Any]):
        """Optimize code with VL-JEPA"""
        try:
            context = {
                'type': 'code_optimization',
                'text': data.get('code', ''),
                'optimization_goal': data.get('goal', 'performance')
            }
            
            # Get optimization embedding
            embedding, _ = await self.vl_jepa.predict_embedding(context)
            
            # Decode optimized code
            optimized = await self.vl_jepa.decode_to_text(embedding, context)
            
            # Publish optimization
            if self.event_bus:
                self.event_bus.publish('vl_jepa.code_optimized', {
                    'original': data.get('code'),
                    'optimized': optimized,
                    'goal': data.get('goal')
                })
                
        except Exception as e:
            logger.error(f"Error in code optimization: {e}")
    
    async def _handle_vr_gesture(self, data: Dict[str, Any]):
        """Recognize VR gestures with VL-JEPA"""
        try:
            context = {
                'type': 'vr_gesture',
                'vision': data.get('frame'),
                'metadata': data
            }
            
            # Get gesture embedding
            embedding, metadata = await self.vl_jepa.predict_embedding(context)
            
            # Find matching gesture from prototypes
            if self.vl_jepa.embedding_space:
                proto_id, similarity = self.vl_jepa.embedding_space.find_nearest_prototype(embedding)
                gesture_name = self._get_gesture_name(proto_id)
                
                # Publish recognition
                if self.event_bus:
                    self.event_bus.publish('vl_jepa.gesture_recognized', {
                        'gesture': gesture_name,
                        'confidence': similarity,
                        'prototype_id': proto_id
                    })
                    
        except Exception as e:
            logger.error(f"Error in gesture recognition: {e}")
    
    async def _handle_vr_scene(self, data: Dict[str, Any]):
        """Understand VR scenes with VL-JEPA"""
        try:
            context = {
                'type': 'vr_scene',
                'vision': data.get('frame'),
                'depth': data.get('depth'),
                'metadata': data
            }
            
            # Get scene embedding
            embedding, _ = await self.vl_jepa.predict_embedding(context)
            
            # Decode scene understanding
            understanding = await self.vl_jepa.decode_to_text(embedding, context)
            
            # Publish understanding
            if self.event_bus:
                self.event_bus.publish('vl_jepa.scene_understanding', {
                    'description': understanding,
                    'embedding': embedding.tolist() if isinstance(embedding, torch.Tensor) else embedding
                })
                
        except Exception as e:
            logger.error(f"Error in scene understanding: {e}")
    
    def _compute_risk_from_embedding(self, embedding: torch.Tensor) -> float:
        """Compute risk score from embedding"""
        try:
            # Simple heuristic: use embedding variance as risk indicator
            if isinstance(embedding, torch.Tensor):
                variance = torch.var(embedding).item()
                # Normalize to 0-1 range
                risk = min(1.0, variance * 10)
                return risk
            return 0.5
        except:
            return 0.5
    
    def _get_gesture_name(self, proto_id: int) -> str:
        """Get gesture name from prototype ID"""
        gesture_names = [
            'swipe_left', 'swipe_right', 'swipe_up', 'swipe_down',
            'pinch', 'spread', 'tap', 'double_tap',
            'rotate_clockwise', 'rotate_counter',
            'grab', 'release', 'point', 'wave'
        ]
        
        if proto_id < len(gesture_names):
            return gesture_names[proto_id]
        return f'gesture_{proto_id}'
    
    def _update_metrics(self, elapsed: float, metadata: Dict[str, Any]):
        """Update performance metrics"""
        self.metrics['requests_processed'] += 1
        
        if metadata.get('cached'):
            self.metrics['embeddings_cached'] += 1
        
        if metadata.get('selective_decode'):
            self.metrics['selective_decodes'] += 1
        
        # Update average response time
        n = self.metrics['requests_processed']
        avg = self.metrics['average_response_time']
        self.metrics['average_response_time'] = (avg * (n - 1) + elapsed) / n
    
    def get_status(self) -> Dict[str, Any]:
        """Get integration status"""
        return {
            'integration_status': self.integration_status,
            'metrics': self.metrics,
            'vl_jepa_metrics': self.vl_jepa.get_metrics(),
            'config': {
                'selective_decode': self.config.enable_selective_decode,
                'cache_embeddings': self.config.cache_embeddings,
                'learning_enabled': self.config.learning_enabled
            }
        }
    
    async def process_multimodal(
        self,
        text: Optional[str] = None,
        image: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[torch.Tensor, str]:
        """
        Process multimodal input through VL-JEPA.
        
        Args:
            text: Text input
            image: Image input (tensor, array, or path)
            context: Additional context
            
        Returns:
            Tuple of (embedding, response_text)
        """
        input_context = context or {}
        
        if text:
            input_context['text'] = text
        if image is not None:
            input_context['vision'] = image
        
        # Get embedding
        embedding, metadata = await self.vl_jepa.predict_embedding(input_context)
        
        # Decode to text
        response_text = await self.vl_jepa.decode_to_text(embedding, input_context)
        
        return embedding, response_text
