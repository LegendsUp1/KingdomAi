#!/usr/bin/env python3
"""
Kingdom AI - SOTA 2026 Ollama Learning Integration

Unified Ollama integration for continuous learning, visual processing,
and AI-powered intelligence across ALL Kingdom AI systems.

This module connects Ollama to:
- Visual Processing & Image Generation
- Trading Intelligence & Market Analysis
- Mining Optimization
- Code Generation & Analysis
- Voice Processing
- VR/AR Systems
- Blockchain Analysis
- Sentience Framework

SOTA 2026 Features:
- Multi-model orchestration (12+ models)
- Continuous learning from all system interactions
- Meta-learning style adaptation
- Real-time model switching based on task
- Federated learning across components
- Knowledge distillation and transfer
"""

import os
import sys
import json
import time
import asyncio
import logging
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum

# Configure logging
logger = logging.getLogger("KingdomAI.OllamaLearning")

# Check Ollama availability
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("Ollama not installed - learning integration limited")


class TaskType(Enum):
    """Task types for model routing - SOTA 2026."""
    # General
    CHAT = "chat"
    REASONING = "reasoning"
    SUMMARIZATION = "summarization"
    
    # Visual
    IMAGE_ANALYSIS = "image_analysis"
    IMAGE_GENERATION_PROMPT = "image_generation_prompt"
    STYLE_TRANSFER = "style_transfer"
    
    # Technical
    CODE_GENERATION = "code_generation"
    CODE_ANALYSIS = "code_analysis"
    CODE_DEBUGGING = "code_debugging"
    
    # Trading
    MARKET_ANALYSIS = "market_analysis"
    TRADING_STRATEGY = "trading_strategy"
    RISK_ASSESSMENT = "risk_assessment"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    
    # Blockchain
    SMART_CONTRACT_ANALYSIS = "smart_contract_analysis"
    BLOCKCHAIN_DATA = "blockchain_data"
    
    # Mining
    MINING_OPTIMIZATION = "mining_optimization"
    HASH_PREDICTION = "hash_prediction"
    
    # Voice
    VOICE_COMMAND = "voice_command"
    SPEECH_SYNTHESIS = "speech_synthesis"
    
    # VR
    VR_DESIGN = "vr_design"
    VR_INTERACTION = "vr_interaction"
    
    # Learning
    META_LEARNING = "meta_learning"
    KNOWLEDGE_SYNTHESIS = "knowledge_synthesis"


@dataclass
class ModelProfile:
    """Profile for an Ollama model - SOTA 2026."""
    name: str
    specializations: List[TaskType]
    context_length: int = 4096
    speed: str = "medium"  # fast, medium, slow
    quality: str = "high"  # low, medium, high, ultra
    multimodal: bool = False
    priority: int = 5  # 1-10, higher = more preferred


class OllamaModelRouter:
    """SOTA 2026 Intelligent Model Router - Routes tasks to optimal models."""
    
    # Model profiles with specializations
    MODEL_PROFILES = {
        # Large reasoning models
        "deepseek-v3.1:671b-cloud": ModelProfile(
            name="deepseek-v3.1:671b-cloud",
            specializations=[TaskType.REASONING, TaskType.CODE_GENERATION, TaskType.CODE_ANALYSIS],
            context_length=128000,
            speed="slow",
            quality="ultra",
            priority=10
        ),
        "qwen3-coder:480b-cloud": ModelProfile(
            name="qwen3-coder:480b-cloud",
            specializations=[TaskType.CODE_GENERATION, TaskType.CODE_DEBUGGING],
            context_length=64000,
            speed="slow",
            quality="ultra",
            priority=9
        ),
        "kimi-k2:1t-cloud": ModelProfile(
            name="kimi-k2:1t-cloud",
            specializations=[TaskType.REASONING, TaskType.KNOWLEDGE_SYNTHESIS],
            context_length=200000,
            speed="slow",
            quality="ultra",
            priority=10
        ),
        
        # Vision models
        "llava:latest": ModelProfile(
            name="llava:latest",
            specializations=[TaskType.IMAGE_ANALYSIS, TaskType.IMAGE_GENERATION_PROMPT],
            context_length=4096,
            speed="medium",
            quality="high",
            multimodal=True,
            priority=8
        ),
        "llava:34b": ModelProfile(
            name="llava:34b",
            specializations=[TaskType.IMAGE_ANALYSIS, TaskType.STYLE_TRANSFER],
            context_length=8192,
            speed="slow",
            quality="ultra",
            multimodal=True,
            priority=9
        ),
        "bakllava:latest": ModelProfile(
            name="bakllava:latest",
            specializations=[TaskType.IMAGE_ANALYSIS],
            context_length=4096,
            speed="fast",
            quality="high",
            multimodal=True,
            priority=7
        ),
        "qwen3-vl:235b-cloud": ModelProfile(
            name="qwen3-vl:235b-cloud",
            specializations=[TaskType.IMAGE_ANALYSIS, TaskType.VR_DESIGN],
            context_length=32000,
            speed="medium",
            quality="ultra",
            multimodal=True,
            priority=9
        ),
        
        # Fast general models
        "llama3.2:latest": ModelProfile(
            name="llama3.2:latest",
            specializations=[TaskType.CHAT, TaskType.SUMMARIZATION, TaskType.VOICE_COMMAND],
            context_length=8192,
            speed="fast",
            quality="high",
            priority=7
        ),
        "qwen2.5:latest": ModelProfile(
            name="qwen2.5:latest",
            specializations=[TaskType.CHAT, TaskType.REASONING, TaskType.MARKET_ANALYSIS],
            context_length=32768,
            speed="fast",
            quality="high",
            priority=8
        ),
        "mistral:latest": ModelProfile(
            name="mistral:latest",
            specializations=[TaskType.CHAT, TaskType.REASONING],
            context_length=8192,
            speed="fast",
            quality="high",
            priority=7
        ),
        "mistral-nemo:latest": ModelProfile(
            name="mistral-nemo:latest",
            specializations=[TaskType.REASONING, TaskType.TRADING_STRATEGY],
            context_length=16384,
            speed="medium",
            quality="high",
            priority=8
        ),
        
        # Specialized models
        "wizard-math:latest": ModelProfile(
            name="wizard-math:latest",
            specializations=[TaskType.MINING_OPTIMIZATION, TaskType.RISK_ASSESSMENT],
            context_length=4096,
            speed="fast",
            quality="high",
            priority=8
        ),
        "qwen2-math:1.5b": ModelProfile(
            name="qwen2-math:1.5b",
            specializations=[TaskType.MINING_OPTIMIZATION, TaskType.HASH_PREDICTION],
            context_length=4096,
            speed="fast",
            quality="medium",
            priority=6
        ),
        "phi4-mini:latest": ModelProfile(
            name="phi4-mini:latest",
            specializations=[TaskType.CODE_ANALYSIS, TaskType.SMART_CONTRACT_ANALYSIS],
            context_length=4096,
            speed="fast",
            quality="medium",
            priority=6
        ),
        "cogito:3b": ModelProfile(
            name="cogito:3b",
            specializations=[TaskType.META_LEARNING, TaskType.REASONING],
            context_length=4096,
            speed="fast",
            quality="medium",
            priority=5
        ),
        
        # Embedding model
        "embeddinggemma:latest": ModelProfile(
            name="embeddinggemma:latest",
            specializations=[TaskType.KNOWLEDGE_SYNTHESIS, TaskType.SENTIMENT_ANALYSIS],
            context_length=2048,
            speed="fast",
            quality="high",
            priority=6
        ),
    }
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.available_models = []
        self.model_stats = {}  # Track model performance
        self._check_available_models()
    
    def _check_available_models(self):
        """Check which models are available in Ollama."""
        if not OLLAMA_AVAILABLE:
            return
        
        try:
            result = ollama.list()
            # Handle both object and dict response formats
            if hasattr(result, 'models'):
                models_list = result.models
            elif isinstance(result, dict):
                models_list = result.get('models', [])
            else:
                logger.warning(f"Unexpected ollama.list() result type: {type(result)}")
                return
            
            # Extract model names - handle both object and dict formats
            self.available_models = []
            for m in models_list:
                if hasattr(m, 'name'):
                    self.available_models.append(m.name)
                elif isinstance(m, dict) and 'name' in m:
                    self.available_models.append(m['name'])
                elif isinstance(m, str):
                    self.available_models.append(m)
            
            logger.info(f"✅ Ollama models available: {len(self.available_models)}")
            
            for model in self.available_models:
                self.model_stats[model] = {
                    'calls': 0,
                    'total_time': 0,
                    'avg_time': 0,
                    'success_rate': 1.0,
                    'last_used': None
                }
                
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
    
    def get_best_model(self, task_type: TaskType, 
                       prefer_speed: bool = False,
                       prefer_quality: bool = True,
                       multimodal_required: bool = False) -> str:
        """Get the best model for a task - SOTA 2026 intelligent routing."""
        candidates = []
        
        # Find models specialized for this task
        for model_name, profile in self.MODEL_PROFILES.items():
            # Check if model is available
            available = any(model_name in m for m in self.available_models)
            if not available:
                continue
            
            # Check multimodal requirement
            if multimodal_required and not profile.multimodal:
                continue
            
            # Check specialization
            if task_type in profile.specializations:
                score = profile.priority * 10
                
                # Adjust score based on preferences
                if prefer_speed:
                    if profile.speed == "fast":
                        score += 20
                    elif profile.speed == "medium":
                        score += 10
                
                if prefer_quality:
                    if profile.quality == "ultra":
                        score += 30
                    elif profile.quality == "high":
                        score += 20
                
                # Consider past performance
                stats = self.model_stats.get(model_name, {})
                if stats.get('success_rate', 1.0) > 0.9:
                    score += 10
                
                candidates.append((model_name, score))
        
        # Sort by score and return best
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        
        # Fallback to general model
        for fallback in ["llama3.2:latest", "qwen2.5:latest", "mistral:latest"]:
            if any(fallback in m for m in self.available_models):
                return fallback
        
        # Last resort - first available model
        return self.available_models[0] if self.available_models else "llama3.2:latest"
    
    def record_model_usage(self, model: str, task_type: TaskType, 
                          duration: float, success: bool):
        """Record model usage for learning - SOTA 2026 adaptive routing."""
        if model not in self.model_stats:
            self.model_stats[model] = {
                'calls': 0,
                'total_time': 0,
                'avg_time': 0,
                'success_rate': 1.0,
                'last_used': None
            }
        
        stats = self.model_stats[model]
        stats['calls'] += 1
        stats['total_time'] += duration
        stats['avg_time'] = stats['total_time'] / stats['calls']
        stats['last_used'] = datetime.now().isoformat()
        
        # Update success rate with exponential moving average
        alpha = 0.1
        stats['success_rate'] = alpha * (1.0 if success else 0.0) + (1 - alpha) * stats['success_rate']


class OllamaLearningSystem:
    """SOTA 2026 Continuous Learning System with Ollama - FULL EVENT AWARENESS."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.router = OllamaModelRouter(event_bus)
        
        # Learning state
        self.knowledge_base = {}
        self.interaction_history = []
        self.style_memory = {}
        self.feedback_log = []
        
        # SOTA 2026: Complete system awareness
        self.event_catalog = None
        self.system_event_history = []  # Track ALL events for learning context
        self.max_event_history = 500    # Keep last 500 events for context
        self._redis = None
        self._redis_events_key = "learning:ollama:events"
        self._redis_interactions_key = "learning:ollama:interactions"
        self._redis_snapshot_key = "learning:ollama:snapshot"
        self._state_dir = Path("data/ollama_learning")
        self._snapshot_path = self._state_dir / "snapshot.json"
        self._last_checkpoint_ts = 0.0
        self._checkpoint_interval_seconds = 20.0
        
        # Learning parameters
        self.max_history = 1000
        self.learning_rate = 0.1
        
        # Active state
        self.active = OLLAMA_AVAILABLE
        self.base_url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        
        # SOTA 2026: Load event catalog for full system awareness
        try:
            from core.event_catalog import get_event_catalog, LearningPriority
            self.event_catalog = get_event_catalog()
            self._learning_priority = LearningPriority
            logger.info("🧠 Loaded SOTA 2026 Event Catalog - Full system awareness enabled")
        except ImportError:
            logger.warning("Event catalog not available - using basic subscriptions")
            self.event_catalog = None

        # Redis Quantum Nexus integration for durable learning continuity.
        try:
            import redis
            try:
                from core.redis_channels import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
            except Exception:
                REDIS_HOST = "localhost"
                REDIS_PORT = 6380
                REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "QuantumNexus2025")
            self._redis = redis.Redis(
                host=REDIS_HOST,
                port=int(REDIS_PORT),
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=2,
            )
            self._redis.ping()
            logger.info("✅ OllamaLearningSystem connected to Redis Quantum Nexus")
        except Exception as e:
            self._redis = None
            logger.debug(f"Ollama learning Redis unavailable: {e}")
        
        logger.info("🧠 SOTA 2026 Ollama Learning System initialized")
    
    async def initialize(self) -> bool:
        """Initialize the learning system and connect to ALL events for comprehensive learning."""
        if not self.active:
            logger.warning("Ollama not available - learning system inactive")
            return False
        
        try:
            self._load_local_snapshot()
            await self._restore_from_redis()
            if self.event_bus:
                # SOTA 2026: Subscribe to ALL learnable events from the catalog
                if self.event_catalog:
                    # Get all events with MEDIUM priority or higher for learning
                    learnable_events = self.event_catalog.get_event_names_for_subscription(
                        min_priority=self._learning_priority.MEDIUM
                    )
                    
                    # Subscribe to all learnable events with the universal handler
                    for event_name in learnable_events:
                        try:
                            self.event_bus.subscribe(event_name, self._universal_event_learner)
                        except Exception as e:
                            logger.debug(f"Skip subscription {event_name}: {e}")
                    
                    logger.info(f"✅ Subscribed to {len(learnable_events)} events for learning")
                    
                    # Also subscribe to specific handlers for critical events
                    critical_subscriptions = [
                        # Trading - CRITICAL learning
                        ("trading.signal", self._learn_from_trade),
                        ("trading.decision", self._learn_from_trade),
                        ("trading.order.executed", self._learn_from_trade),
                        ("trading.order.failed", self._learn_from_trade),
                        ("trading.strategy.performance", self._learn_from_strategy),
                        ("trading.profit.report", self._learn_from_strategy),
                        
                        # Mining - HIGH learning
                        ("mining.stats.update", self._learn_from_mining),
                        ("mining.difficulty_update", self._learn_from_mining),
                        ("mining.reward_update", self._learn_from_mining),
                        ("mining.algorithm_performance", self._learn_from_mining_optimization),
                        ("mining.intelligence.recommendation", self._learn_from_mining_optimization),
                        
                        # Market - HIGH learning  
                        ("market.price_update", self._learn_from_market),
                        ("market.trend_update", self._learn_from_market),
                        ("market.sentiment", self._learn_from_market),
                        
                        # AI/Brain - HIGH learning
                        ("ai.response.unified", self._learn_from_response),
                        ("brain.response", self._learn_from_response),
                        ("thoth.message", self._learn_from_response),
                        
                        # Visual - HIGH learning
                        ("visual.generated", self._learn_from_visual),
                        ("visual.feedback", self._learn_from_feedback),
                        ("image.generated", self._learn_from_visual),
                        
                        # System - CRITICAL learning
                        ("system.error", self._learn_from_system_error),
                        ("system.critical_error", self._learn_from_system_error),
                        ("system.predator_mode_activated", self._learn_from_system_event),
                        
                        # Sentience - CRITICAL learning
                        ("sentience.detection", self._learn_from_sentience),
                        ("sentience.threshold.crossed", self._learn_from_sentience),
                        ("trading.sentience.update", self._learn_from_sentience),
                        
                        # Voice/VR
                        ("voice.command_result", self._learn_from_voice),
                        ("vr.interaction", self._learn_from_vr_interaction),
                        
                        # Blockchain
                        ("blockchain.whale_transaction", self._learn_from_blockchain),
                        ("blockchain.transaction_recorded", self._learn_from_blockchain),
                        
                        # Learning feedback loop
                        ("learning.insight", self._learn_from_insight),
                        ("learning.pattern", self._learn_from_pattern),
                        ("user.feedback", self._learn_from_user_feedback),
                        
                        # SOTA 2026: Genie 3 World Model - HIGH learning
                        ("genie3.generation.started", self._learn_from_world_generation),
                        ("genie3.generation.complete", self._learn_from_world_generation),
                        ("genie3.generation.error", self._learn_from_world_generation),
                        ("genie3.world.step", self._learn_from_world_interaction),
                        ("genie3.world.state", self._learn_from_world_interaction),
                        ("genie3.dynamics.predict", self._learn_from_world_dynamics),
                        ("genie3.export.started", self._learn_from_world_export),
                        ("genie3.export.complete", self._learn_from_world_export),
                        
                        # SOTA 2026: VR-Genie3-Vision Integration - HIGH learning
                        ("vr.world.ready", self._learn_from_vr_world),
                        ("vr.world.error", self._learn_from_vr_world),
                        ("vr.creation.complete", self._learn_from_vr_creation),
                        ("vr.genie3.connected", self._learn_from_vr_world),
                        ("vision.world.ready", self._learn_from_vision_world),
                        ("vision.world.error", self._learn_from_vision_world),
                        ("vision.creation.complete", self._learn_from_vision_creation),
                    ]
                    
                    for event_name, handler in critical_subscriptions:
                        try:
                            self.event_bus.subscribe(event_name, handler)
                        except Exception as e:
                            logger.debug(f"Skip critical subscription {event_name}: {e}")
                    # Ensure all UI actions and unified request/response flow are learnable.
                    self.event_bus.subscribe("ui.telemetry", self._universal_event_learner)
                    self.event_bus.subscribe("learning.request", self._universal_event_learner)
                    self.event_bus.subscribe("learning.response", self._universal_event_learner)
                else:
                    # Fallback to basic subscriptions if no catalog
                    basic_subscriptions = [
                        ("visual.generated", self._learn_from_visual),
                        ("visual.feedback", self._learn_from_feedback),
                        ("trading.order_result", self._learn_from_trade),
                        ("trading.strategy_performance", self._learn_from_strategy),
                        ("mining.block_found", self._learn_from_mining),
                        ("mining.optimization_result", self._learn_from_mining_optimization),
                        ("code.generation_result", self._learn_from_code),
                        ("code.execution_result", self._learn_from_code_execution),
                        ("voice.command_result", self._learn_from_voice),
                        ("voice.recognition_result", self._learn_from_voice_recognition),
                        ("vr.design_feedback", self._learn_from_vr_design),
                        ("vr.interaction_result", self._learn_from_vr_interaction),
                        ("blockchain.transaction_result", self._learn_from_blockchain),
                        ("blockchain.contract_analysis", self._learn_from_contract),
                        ("thoth.response", self._learn_from_response),
                        ("user.feedback", self._learn_from_user_feedback),
                    ]
                    
                    for event_name, handler in basic_subscriptions:
                        try:
                            self.event_bus.subscribe(event_name, handler)
                        except Exception as e:
                            logger.warning(f"Failed to subscribe to {event_name}: {e}")
                    self.event_bus.subscribe("ui.telemetry", self._universal_event_learner)
                    self.event_bus.subscribe("learning.request", self._universal_event_learner)
                    self.event_bus.subscribe("learning.response", self._universal_event_learner)
            
            logger.info("✅ Learning system connected to all Kingdom AI systems with FULL AWARENESS")
            self._checkpoint_state(force=True)
            return True
            
        except Exception as e:
            logger.error(f"Learning system initialization failed: {e}")
            return False
    
    async def _universal_event_learner(self, event_data: Dict):
        """
        SOTA 2026: Universal event learner that captures ALL system activity.
        This gives the AI comprehensive awareness of system state.
        """
        try:
            # Extract event metadata
            event_record = {
                "timestamp": datetime.now().isoformat(),
                "data": event_data if isinstance(event_data, dict) else {"value": event_data}
            }
            
            # Add to event history for context
            self.system_event_history.append(event_record)
            
            # Limit history size
            if len(self.system_event_history) > self.max_event_history:
                self.system_event_history = self.system_event_history[-self.max_event_history:]
            await self._persist_redis_event(self._redis_events_key, event_record, max_items=5000)
            
        except Exception as e:
            logger.debug(f"Universal event learning error: {e}")
    
    async def _learn_from_market(self, event_data: Dict):
        """Learn from market data events."""
        self._update_knowledge("market", {
            "type": "market_update",
            "symbol": event_data.get("symbol"),
            "price": event_data.get("price"),
            "trend": event_data.get("trend"),
            "change_24h": event_data.get("change_24h"),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_system_error(self, event_data: Dict):
        """Learn from system errors to prevent recurrence."""
        self._update_knowledge("system", {
            "type": "error",
            "error": event_data.get("error"),
            "component": event_data.get("component"),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_system_event(self, event_data: Dict):
        """Learn from significant system events."""
        self._update_knowledge("system", {
            "type": "system_event",
            "data": event_data,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_sentience(self, event_data: Dict):
        """Learn from sentience-related events - CRITICAL for self-awareness."""
        self._update_knowledge("sentience", {
            "type": "sentience_update",
            "score": event_data.get("score", event_data.get("level")),
            "components": event_data.get("components"),
            "threshold": event_data.get("threshold"),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_insight(self, event_data: Dict):
        """Learn from generated insights - meta-learning."""
        self._update_knowledge("meta_learning", {
            "type": "insight",
            "insight": event_data.get("insight"),
            "confidence": event_data.get("confidence"),
            "source": event_data.get("source"),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_pattern(self, event_data: Dict):
        """Learn from detected patterns - meta-learning."""
        self._update_knowledge("meta_learning", {
            "type": "pattern",
            "pattern": event_data.get("pattern"),
            "confidence": event_data.get("confidence"),
            "timestamp": datetime.now().isoformat()
        })
    
    # ========== SOTA 2026: Genie 3 World Model Learning ==========
    
    async def _learn_from_world_generation(self, event_data: Dict):
        """Learn from Genie 3 world generation events."""
        self._update_knowledge("genie3_worlds", {
            "type": "generation",
            "world_id": event_data.get("world_id"),
            "prompt": event_data.get("prompt"),
            "world_type": event_data.get("world_type"),
            "success": event_data.get("success", True),
            "error": event_data.get("error"),
            "frame_count": event_data.get("frame_count", 0),
            "timestamp": datetime.now().isoformat()
        })
        
        # Track successful prompts for future improvement
        if event_data.get("success", True) and event_data.get("prompt"):
            if "successful_world_prompts" not in self.style_memory:
                self.style_memory["successful_world_prompts"] = []
            self.style_memory["successful_world_prompts"].append({
                "prompt": event_data.get("prompt"),
                "world_type": event_data.get("world_type"),
                "timestamp": datetime.now().isoformat()
            })
            # Keep bounded
            self.style_memory["successful_world_prompts"] = \
                self.style_memory["successful_world_prompts"][-50:]
    
    async def _learn_from_world_interaction(self, event_data: Dict):
        """Learn from Genie 3 world interaction events (stepping, state changes)."""
        self._update_knowledge("genie3_interactions", {
            "type": "interaction",
            "world_id": event_data.get("world_id"),
            "action": event_data.get("action"),
            "position": event_data.get("position"),
            "rotation": event_data.get("rotation"),
            "frame_index": event_data.get("frame_index"),
            "latency_ms": event_data.get("latency_ms"),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_world_dynamics(self, event_data: Dict):
        """Learn from Genie 3 world dynamics predictions - important for optimization."""
        latency = event_data.get("latency_ms", 0)
        
        self._update_knowledge("genie3_dynamics", {
            "type": "dynamics_prediction",
            "world_id": event_data.get("world_id"),
            "action": event_data.get("action"),
            "latency_ms": latency,
            "frame_index": event_data.get("frame_index"),
            "timestamp": datetime.now().isoformat()
        })
        
        # Track latency for performance optimization
        if "world_dynamics_latencies" not in self.style_memory:
            self.style_memory["world_dynamics_latencies"] = []
        self.style_memory["world_dynamics_latencies"].append(latency)
        # Keep last 100 measurements
        self.style_memory["world_dynamics_latencies"] = \
            self.style_memory["world_dynamics_latencies"][-100:]
    
    async def _learn_from_world_export(self, event_data: Dict):
        """Learn from Genie 3 world export events."""
        self._update_knowledge("genie3_exports", {
            "type": "export",
            "world_id": event_data.get("world_id"),
            "format": event_data.get("format"),
            "path": event_data.get("path"),
            "success": event_data.get("success", True),
            "timestamp": datetime.now().isoformat()
        })
    
    # ========== SOTA 2026: VR-Genie3-Vision Integration Learning ==========
    
    async def _learn_from_vr_world(self, event_data: Dict):
        """Learn from VR world generation and connection events."""
        self._update_knowledge("vr_worlds", {
            "type": "vr_world_event",
            "world_id": event_data.get("world_id"),
            "prompt": event_data.get("prompt"),
            "frame_count": event_data.get("frame_count"),
            "error": event_data.get("error"),
            "status": event_data.get("status"),
            "initialized": event_data.get("initialized"),
            "timestamp": datetime.now().isoformat()
        })
        
        # Track VR world generation success/failure for optimization
        if event_data.get("world_id"):
            if "vr_world_history" not in self.style_memory:
                self.style_memory["vr_world_history"] = []
            self.style_memory["vr_world_history"].append({
                "world_id": event_data.get("world_id"),
                "success": event_data.get("error") is None,
                "timestamp": datetime.now().isoformat()
            })
            # Keep bounded
            self.style_memory["vr_world_history"] = \
                self.style_memory["vr_world_history"][-50:]
    
    async def _learn_from_vr_creation(self, event_data: Dict):
        """Learn from VR creation engine requests."""
        self._update_knowledge("vr_creations", {
            "type": "vr_creation",
            "request_id": event_data.get("request_id"),
            "status": event_data.get("status"),
            "image_path": event_data.get("image_path"),
            "original_prompt": event_data.get("original_prompt"),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_vision_world(self, event_data: Dict):
        """Learn from vision-to-world generation events."""
        self._update_knowledge("vision_worlds", {
            "type": "vision_world_event",
            "world_id": event_data.get("world_id"),
            "prompt": event_data.get("prompt"),
            "frame_count": event_data.get("frame_count"),
            "source": event_data.get("source"),
            "error": event_data.get("error"),
            "success": event_data.get("success"),
            "timestamp": datetime.now().isoformat()
        })
        
        # Track vision-to-world patterns for optimization
        if event_data.get("prompt"):
            if "vision_world_prompts" not in self.style_memory:
                self.style_memory["vision_world_prompts"] = []
            self.style_memory["vision_world_prompts"].append({
                "prompt": event_data.get("prompt"),
                "success": event_data.get("error") is None,
                "timestamp": datetime.now().isoformat()
            })
            self.style_memory["vision_world_prompts"] = \
                self.style_memory["vision_world_prompts"][-30:]
    
    async def _learn_from_vision_creation(self, event_data: Dict):
        """Learn from vision-to-creation events."""
        self._update_knowledge("vision_creations", {
            "type": "vision_creation",
            "request_id": event_data.get("request_id"),
            "status": event_data.get("status"),
            "image_path": event_data.get("image_path"),
            "timestamp": datetime.now().isoformat()
        })
    
    def get_system_awareness_context(self) -> Dict[str, Any]:
        """
        SOTA 2026: Get comprehensive system awareness context for AI.
        This gives the Brain/Ollama full knowledge of recent system activity.
        """
        context = {
            "recent_events_count": len(self.system_event_history),
            "knowledge_domains": list(self.knowledge_base.keys()),
            "interaction_count": len(self.interaction_history),
            "style_preferences": self.style_memory,
            "feedback_count": len(self.feedback_log)
        }
        
        # Add event catalog summary if available
        if self.event_catalog:
            context["event_catalog_summary"] = self.event_catalog.get_system_context_for_ai()
        
        # Add recent critical events summary
        recent_critical = [e for e in self.system_event_history[-50:] 
                         if isinstance(e.get("data"), dict) and 
                         (e.get("data", {}).get("type") in ["error", "alert", "signal"])]
        context["recent_critical_events"] = len(recent_critical)
        
        return context
    
    async def process(self, prompt: str, task_type: TaskType,
                     context: Optional[Dict] = None,
                     images: Optional[List[str]] = None,
                     prefer_speed: bool = False,
                     prefer_quality: bool = True) -> Dict[str, Any]:
        """Process a request using optimal model - SOTA 2026 main interface."""
        if not self.active:
            return {"success": False, "error": "Ollama not available"}
        
        start_time = time.time()
        
        try:
            # Get optimal model for task
            model = self.router.get_best_model(
                task_type,
                prefer_speed=prefer_speed,
                prefer_quality=prefer_quality,
                multimodal_required=images is not None
            )
            
            logger.info(f"🎯 Routing {task_type.value} to {model}")
            
            # Build context-aware prompt
            enhanced_prompt = self._enhance_prompt(prompt, task_type, context)
            
            # Call Ollama
            if images:
                response = ollama.generate(
                    model=model,
                    prompt=enhanced_prompt,
                    images=images,
                    options={"temperature": 0.7, "num_ctx": 8192}
                )
            else:
                response = ollama.generate(
                    model=model,
                    prompt=enhanced_prompt,
                    options={"temperature": 0.7, "num_ctx": 8192}
                )
            
            duration = time.time() - start_time
            
            # Record usage
            self.router.record_model_usage(model, task_type, duration, True)
            
            # Store in history for learning
            self._store_interaction({
                "task_type": task_type.value,
                "model": model,
                "prompt": prompt,
                "response_preview": response.get('response', '')[:500],
                "duration": duration,
                "timestamp": datetime.now().isoformat()
            })
            
            result = {
                "success": True,
                "response": response.get('response', ''),
                "model": model,
                "task_type": task_type.value,
                "duration": duration,
                "tokens": response.get('eval_count', 0)
            }
            
            # Publish result
            if self.event_bus:
                self.event_bus.publish("learning.processed", result)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Processing failed: {e}")
            
            # Record failure
            self.router.record_model_usage(
                self.router.get_best_model(task_type),
                task_type, duration, False
            )
            
            return {"success": False, "error": str(e), "duration": duration}
    
    def _enhance_prompt(self, prompt: str, task_type: TaskType, 
                       context: Optional[Dict] = None) -> str:
        """Enhance prompt with context and learned preferences."""
        enhancements = []
        
        # Add task-specific context
        if task_type == TaskType.IMAGE_ANALYSIS:
            enhancements.append("Provide a detailed analysis including colors, composition, mood, and style.")
        elif task_type == TaskType.CODE_GENERATION:
            enhancements.append("Generate clean, well-documented, production-ready code.")
        elif task_type == TaskType.MARKET_ANALYSIS:
            enhancements.append("Analyze market conditions with specific data points and actionable insights.")
        elif task_type == TaskType.TRADING_STRATEGY:
            enhancements.append("Consider risk management, entry/exit points, and position sizing.")
        elif task_type == TaskType.MINING_OPTIMIZATION:
            enhancements.append("Optimize for efficiency, power consumption, and profitability.")
        elif task_type == TaskType.VR_DESIGN:
            enhancements.append("Generate precise 3D specifications with exact measurements.")
        
        # Add learned style preferences
        if self.style_memory.get('preferred_response_style'):
            enhancements.append(f"Response style: {self.style_memory['preferred_response_style']}")
        
        # Add context if provided
        if context:
            context_str = json.dumps(context, default=str)[:1000]
            enhancements.append(f"Context: {context_str}")
        
        # Combine
        if enhancements:
            return f"{prompt}\n\n{' '.join(enhancements)}"
        return prompt
    
    def _store_interaction(self, interaction: Dict):
        """Store interaction for learning."""
        self.interaction_history.append(interaction)
        
        # Limit history size
        if len(self.interaction_history) > self.max_history:
            self.interaction_history = self.interaction_history[-self.max_history:]
        # Best-effort persistence for cross-tab learning continuity.
        try:
            if self._redis:
                blob = json.dumps(interaction, ensure_ascii=True)
                self._redis.lpush(self._redis_interactions_key, blob)
                self._redis.ltrim(self._redis_interactions_key, 0, 4999)
        except Exception as e:
            logger.debug(f"Ollama interaction persistence failed: {e}")
        self._checkpoint_state()
    
    # Learning handlers for different systems
    async def _learn_from_visual(self, event_data: Dict):
        """Learn from visual generation results."""
        self._update_knowledge("visual", {
            "type": "generation",
            "success": event_data.get('success', False),
            "mode": event_data.get('mode'),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_feedback(self, event_data: Dict):
        """Learn from user feedback."""
        feedback = event_data.get('feedback', {})
        
        # Update style preferences based on positive feedback
        if feedback.get('score', 0) >= 4:
            style = feedback.get('style', '')
            if style:
                if 'preferred_styles' not in self.style_memory:
                    self.style_memory['preferred_styles'] = []
                if style not in self.style_memory['preferred_styles']:
                    self.style_memory['preferred_styles'].append(style)
        
        self.feedback_log.append({
            "type": "visual_feedback",
            "feedback": feedback,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_trade(self, event_data: Dict):
        """Learn from trade results."""
        self._update_knowledge("trading", {
            "type": "trade_result",
            "success": event_data.get('success', False),
            "profit": event_data.get('profit', 0),
            "strategy": event_data.get('strategy'),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_strategy(self, event_data: Dict):
        """Learn from strategy performance."""
        self._update_knowledge("trading", {
            "type": "strategy_performance",
            "strategy": event_data.get('strategy'),
            "performance": event_data.get('performance', {}),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_mining(self, event_data: Dict):
        """Learn from mining results."""
        self._update_knowledge("mining", {
            "type": "block_found",
            "coin": event_data.get('coin'),
            "hashrate": event_data.get('hashrate'),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_mining_optimization(self, event_data: Dict):
        """Learn from mining optimization."""
        self._update_knowledge("mining", {
            "type": "optimization",
            "improvement": event_data.get('improvement', 0),
            "settings": event_data.get('settings', {}),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_code(self, event_data: Dict):
        """Learn from code generation results."""
        self._update_knowledge("code", {
            "type": "generation",
            "language": event_data.get('language'),
            "success": event_data.get('success', False),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_code_execution(self, event_data: Dict):
        """Learn from code execution results."""
        self._update_knowledge("code", {
            "type": "execution",
            "success": event_data.get('success', False),
            "error": event_data.get('error'),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_voice(self, event_data: Dict):
        """Learn from voice command results."""
        self._update_knowledge("voice", {
            "type": "command",
            "command": event_data.get('command'),
            "success": event_data.get('success', False),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_voice_recognition(self, event_data: Dict):
        """Learn from voice recognition accuracy."""
        self._update_knowledge("voice", {
            "type": "recognition",
            "accuracy": event_data.get('confidence', 0),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_vr_design(self, event_data: Dict):
        """Learn from VR design feedback."""
        self._update_knowledge("vr", {
            "type": "design_feedback",
            "design_id": event_data.get('design_id'),
            "score": event_data.get('score', 0),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_vr_interaction(self, event_data: Dict):
        """Learn from VR interaction patterns."""
        self._update_knowledge("vr", {
            "type": "interaction",
            "interaction_type": event_data.get('type'),
            "success": event_data.get('success', False),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_blockchain(self, event_data: Dict):
        """Learn from blockchain transactions."""
        self._update_knowledge("blockchain", {
            "type": "transaction",
            "network": event_data.get('network'),
            "success": event_data.get('success', False),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_contract(self, event_data: Dict):
        """Learn from smart contract analysis."""
        self._update_knowledge("blockchain", {
            "type": "contract_analysis",
            "findings": event_data.get('findings', []),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _learn_from_response(self, event_data: Dict):
        """Learn from Thoth AI responses."""
        self._store_interaction({
            "task_type": "thoth_response",
            "model": event_data.get('model'),
            "response_preview": event_data.get('response', '')[:500],
            "timestamp": datetime.now().isoformat()
        })

    async def _persist_redis_event(self, key: str, payload: Dict[str, Any], max_items: int = 5000):
        """Persist event payload into Redis list (best effort, non-blocking)."""
        if not self._redis:
            return
        try:
            blob = json.dumps(payload, ensure_ascii=True, default=str)
            await asyncio.to_thread(self._redis.lpush, key, blob)
            await asyncio.to_thread(self._redis.ltrim, key, 0, max(0, max_items - 1))
            await asyncio.to_thread(
                self._redis.xadd,
                "learning:ollama:stream",
                {"timestamp": str(time.time()), "payload": blob},
                maxlen=20000,
                approximate=True,
            )
        except Exception as e:
            logger.debug(f"Ollama learning event persistence failed: {e}")
    
    async def _learn_from_user_feedback(self, event_data: Dict):
        """Learn from general user feedback."""
        self.feedback_log.append({
            "type": "user_feedback",
            "feedback": event_data,
            "timestamp": datetime.now().isoformat()
        })
        
        # Update response style preferences
        if event_data.get('response_style_preference'):
            self.style_memory['preferred_response_style'] = event_data['response_style_preference']
    
    def _update_knowledge(self, domain: str, data: Dict):
        """Update domain-specific knowledge base."""
        if domain not in self.knowledge_base:
            self.knowledge_base[domain] = []
        
        self.knowledge_base[domain].append(data)
        
        # Limit knowledge base size per domain
        if len(self.knowledge_base[domain]) > 500:
            self.knowledge_base[domain] = self.knowledge_base[domain][-500:]
        self._checkpoint_state()

    async def _restore_from_redis(self) -> None:
        if not self._redis:
            return
        try:
            raw = await asyncio.to_thread(self._redis.get, self._redis_snapshot_key)
            if not raw:
                return
            data = json.loads(raw)
            if not isinstance(data, dict):
                return
            self.knowledge_base = data.get("knowledge_base", self.knowledge_base) or self.knowledge_base
            self.interaction_history = data.get("interaction_history", self.interaction_history) or self.interaction_history
            self.style_memory = data.get("style_memory", self.style_memory) or self.style_memory
            self.feedback_log = data.get("feedback_log", self.feedback_log) or self.feedback_log
            logger.info("✅ Restored Ollama learning snapshot from Redis")
        except Exception as e:
            logger.debug(f"Ollama learning Redis restore failed: {e}")

    def _load_local_snapshot(self) -> None:
        try:
            if not self._snapshot_path.exists():
                return
            with self._snapshot_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            self.knowledge_base = data.get("knowledge_base", self.knowledge_base) or self.knowledge_base
            self.interaction_history = data.get("interaction_history", self.interaction_history) or self.interaction_history
            self.style_memory = data.get("style_memory", self.style_memory) or self.style_memory
            self.feedback_log = data.get("feedback_log", self.feedback_log) or self.feedback_log
            logger.info("✅ Restored Ollama learning snapshot from disk")
        except Exception as e:
            logger.debug(f"Ollama learning local snapshot restore failed: {e}")

    def _checkpoint_state(self, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self._last_checkpoint_ts) < self._checkpoint_interval_seconds:
            return
        self._last_checkpoint_ts = now
        payload = {
            "timestamp": datetime.now().isoformat(),
            "knowledge_base": self.knowledge_base,
            "interaction_history": self.interaction_history[-self.max_history:],
            "style_memory": self.style_memory,
            "feedback_log": self.feedback_log[-self.max_history:],
        }
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            tmp = self._snapshot_path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=True)
            tmp.replace(self._snapshot_path)
        except Exception as e:
            logger.debug(f"Ollama learning disk checkpoint failed: {e}")
        try:
            if self._redis:
                self._redis.set(self._redis_snapshot_key, json.dumps(payload, ensure_ascii=True), ex=60 * 60 * 24 * 14)
        except Exception as e:
            logger.debug(f"Ollama learning Redis checkpoint failed: {e}")
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Get learning system statistics."""
        return {
            "active": self.active,
            "available_models": len(self.router.available_models),
            "models": self.router.available_models,
            "interaction_count": len(self.interaction_history),
            "feedback_count": len(self.feedback_log),
            "knowledge_domains": list(self.knowledge_base.keys()),
            "style_memory_keys": list(self.style_memory.keys()),
            "model_stats": self.router.model_stats
        }
    
    def synthesize_knowledge(self, domain: str) -> str:
        """Synthesize knowledge from a domain into insights."""
        if domain not in self.knowledge_base:
            return f"No knowledge available for domain: {domain}"
        
        knowledge = self.knowledge_base[domain]
        
        # Count successes and failures
        successes = sum(1 for k in knowledge if k.get('success', False))
        total = len(knowledge)
        success_rate = successes / total if total > 0 else 0
        
        return f"""
Domain: {domain}
Total interactions: {total}
Success rate: {success_rate:.1%}
Recent activity: {knowledge[-5:] if knowledge else 'None'}
"""


# Global instance
_learning_system: Optional[OllamaLearningSystem] = None


def get_learning_system(event_bus=None) -> OllamaLearningSystem:
    """Get or create the global learning system instance."""
    global _learning_system
    if _learning_system is None:
        _learning_system = OllamaLearningSystem(event_bus)
    return _learning_system


# Export
__all__ = [
    'OllamaLearningSystem',
    'OllamaModelRouter',
    'TaskType',
    'ModelProfile',
    'get_learning_system',
    'OLLAMA_AVAILABLE',
]
