#!/usr/bin/env python3
"""
Kingdom AI - SOTA 2026 Event Catalog

Complete catalog of ALL events in the Kingdom AI system.
This catalog is used by the Brain/AI systems to understand and learn from all system activity.

SOTA 2026 Features:
- Complete event documentation (300+ subscribed, 500+ published)
- Event categorization for intelligent learning
- Priority levels for learning focus
- Cross-system event mapping
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger("KingdomAI.EventCatalog")


class EventCategory(Enum):
    """Categories of events in the Kingdom AI system."""
    AI = "ai"
    TRADING = "trading"
    MINING = "mining"
    MARKET = "market"
    BLOCKCHAIN = "blockchain"
    VOICE = "voice"
    VR = "vr"
    SYSTEM = "system"
    LEARNING = "learning"
    SECURITY = "security"
    WALLET = "wallet"
    THOTH = "thoth"
    CREATIVE = "creative"
    COMMS = "comms"
    HARDWARE = "hardware"
    UI = "ui"
    API = "api"
    NAVIGATION = "navigation"
    SETTINGS = "settings"
    STRATEGY = "strategy"
    RISK = "risk"
    QUANTUM = "quantum"
    SENTIENCE = "sentience"
    UNITY = "unity"


class LearningPriority(Enum):
    """Priority for learning from events."""
    CRITICAL = 5  # Always learn from these
    HIGH = 4      # Learn with high frequency
    MEDIUM = 3    # Normal learning
    LOW = 2       # Learn occasionally
    DEBUG = 1     # Only for debugging


@dataclass
class EventDefinition:
    """Definition of an event in the system."""
    name: str
    category: EventCategory
    learning_priority: LearningPriority
    description: str = ""
    data_fields: List[str] = field(default_factory=list)
    publishers: List[str] = field(default_factory=list)
    subscribers: List[str] = field(default_factory=list)


class KingdomEventCatalog:
    """
    SOTA 2026 Complete Event Catalog for Kingdom AI.
    
    This catalog enables the Brain/Ollama systems to:
    1. Understand all system events
    2. Learn from relevant events
    3. Correlate cross-system activity
    4. Generate intelligent responses with full system awareness
    """
    
    # ========== AI EVENTS ==========
    AI_EVENTS = {
        # Core AI routing
        "ai.request": EventDefinition("ai.request", EventCategory.AI, LearningPriority.HIGH,
            "AI request for processing", ["message", "context", "request_id", "source"]),
        "ai.response": EventDefinition("ai.response", EventCategory.AI, LearningPriority.HIGH,
            "AI response from processing", ["response", "model", "request_id"]),
        "ai.response.unified": EventDefinition("ai.response.unified", EventCategory.AI, LearningPriority.HIGH,
            "Unified AI response from brain router", ["response", "model", "request_id", "source"]),
        "ai.response.delta": EventDefinition("ai.response.delta", EventCategory.AI, LearningPriority.MEDIUM,
            "Streaming AI response chunk", ["delta", "request_id"]),
        "ai.error": EventDefinition("ai.error", EventCategory.AI, LearningPriority.CRITICAL,
            "AI processing error", ["error", "request_id"]),
        "ai.model.load": EventDefinition("ai.model.load", EventCategory.AI, LearningPriority.MEDIUM,
            "AI model loaded", ["model", "size", "capabilities"]),
        "ai.status": EventDefinition("ai.status", EventCategory.AI, LearningPriority.LOW,
            "AI system status update", ["status", "models_available"]),
        
        # AI analysis
        "ai.analysis.complete": EventDefinition("ai.analysis.complete", EventCategory.AI, LearningPriority.HIGH,
            "AI analysis completed", ["analysis", "type", "symbol"]),
        "ai.analysis.start_24h": EventDefinition("ai.analysis.start_24h", EventCategory.AI, LearningPriority.MEDIUM,
            "24-hour learning analysis started", ["timestamp"]),
        
        # AI autotrade
        "ai.autotrade.plan.generated": EventDefinition("ai.autotrade.plan.generated", EventCategory.AI, LearningPriority.HIGH,
            "AI generated trading plan", ["plan", "symbols", "confidence"]),
        "ai.autotrade.crypto.enable": EventDefinition("ai.autotrade.crypto.enable", EventCategory.AI, LearningPriority.MEDIUM,
            "Crypto auto-trading enabled", []),
        "ai.autotrade.stocks.enable": EventDefinition("ai.autotrade.stocks.enable", EventCategory.AI, LearningPriority.MEDIUM,
            "Stocks auto-trading enabled", []),
            
        # AI commands
        "ai.command.execute": EventDefinition("ai.command.execute", EventCategory.AI, LearningPriority.HIGH,
            "AI command execution request", ["command", "args"]),
        "ai.command.executed": EventDefinition("ai.command.executed", EventCategory.AI, LearningPriority.HIGH,
            "AI command executed", ["command", "result", "success"]),
        "ai.generate": EventDefinition("ai.generate", EventCategory.AI, LearningPriority.MEDIUM,
            "AI generation request", ["prompt", "type"]),
        "ai.query": EventDefinition("ai.query", EventCategory.AI, LearningPriority.MEDIUM,
            "AI query request", ["query", "context"]),
    }
    
    # ========== TRADING EVENTS ==========
    TRADING_EVENTS = {
        # Core trading
        "trading.signal": EventDefinition("trading.signal", EventCategory.TRADING, LearningPriority.CRITICAL,
            "Trading signal generated", ["symbol", "direction", "confidence", "strategy"]),
        "trading.decision": EventDefinition("trading.decision", EventCategory.TRADING, LearningPriority.CRITICAL,
            "Trading decision made", ["symbol", "action", "size", "price"]),
        "trading.order": EventDefinition("trading.order", EventCategory.TRADING, LearningPriority.CRITICAL,
            "Trading order submitted", ["symbol", "side", "size", "price", "order_id"]),
        "trading.order.executed": EventDefinition("trading.order.executed", EventCategory.TRADING, LearningPriority.CRITICAL,
            "Trading order executed", ["order_id", "fill_price", "fill_size"]),
        "trading.order.failed": EventDefinition("trading.order.failed", EventCategory.TRADING, LearningPriority.CRITICAL,
            "Trading order failed", ["order_id", "error"]),
        "trading.order_filled": EventDefinition("trading.order_filled", EventCategory.TRADING, LearningPriority.CRITICAL,
            "Order filled notification", ["order_id", "symbol", "price", "quantity"]),
            
        # Intelligence
        "trading.intelligence.opportunity": EventDefinition("trading.intelligence.opportunity", EventCategory.TRADING, LearningPriority.HIGH,
            "Trading opportunity detected", ["symbol", "type", "score", "reason"]),
        "trading.intelligence.alert": EventDefinition("trading.intelligence.alert", EventCategory.TRADING, LearningPriority.HIGH,
            "Trading alert triggered", ["alert_type", "symbol", "message"]),
        "trading.intelligence.insight": EventDefinition("trading.intelligence.insight", EventCategory.TRADING, LearningPriority.HIGH,
            "Trading insight generated", ["insight", "confidence"]),
        "trading.opportunities.high_value": EventDefinition("trading.opportunities.high_value", EventCategory.TRADING, LearningPriority.CRITICAL,
            "High-value trading opportunities", ["opportunities", "count"]),
            
        # Market data
        "trading.live_prices": EventDefinition("trading.live_prices", EventCategory.TRADING, LearningPriority.MEDIUM,
            "Live price update", ["symbol", "price", "volume"]),
        "trading.market_data_update": EventDefinition("trading.market_data_update", EventCategory.TRADING, LearningPriority.MEDIUM,
            "Market data update", ["data"]),
        "trading.order_book_update": EventDefinition("trading.order_book_update", EventCategory.TRADING, LearningPriority.LOW,
            "Order book update", ["symbol", "bids", "asks"]),
            
        # Strategy
        "trading.strategy.activated": EventDefinition("trading.strategy.activated", EventCategory.TRADING, LearningPriority.HIGH,
            "Trading strategy activated", ["strategy", "params"]),
        "trading.strategy.stopped": EventDefinition("trading.strategy.stopped", EventCategory.TRADING, LearningPriority.HIGH,
            "Trading strategy stopped", ["strategy", "reason"]),
        "trading.strategy.performance": EventDefinition("trading.strategy.performance", EventCategory.TRADING, LearningPriority.CRITICAL,
            "Strategy performance update", ["strategy", "pnl", "win_rate", "sharpe"]),
            
        # Auto trading
        "trading.auto_trade.started": EventDefinition("trading.auto_trade.started", EventCategory.TRADING, LearningPriority.HIGH,
            "Auto trading started", ["config"]),
        "trading.auto_trade.stopped": EventDefinition("trading.auto_trade.stopped", EventCategory.TRADING, LearningPriority.HIGH,
            "Auto trading stopped", ["reason"]),
            
        # Profit tracking
        "trading.profit.report": EventDefinition("trading.profit.report", EventCategory.TRADING, LearningPriority.CRITICAL,
            "Profit report", ["total_pnl", "realized", "unrealized"]),
        "trading.profit.update": EventDefinition("trading.profit.update", EventCategory.TRADING, LearningPriority.HIGH,
            "Profit update", ["pnl", "change"]),
            
        # Analysis
        "trading.analysis.response": EventDefinition("trading.analysis.response", EventCategory.TRADING, LearningPriority.HIGH,
            "Trading analysis response", ["symbol", "analysis"]),
        "trading.sentiment.snapshot": EventDefinition("trading.sentiment.snapshot", EventCategory.TRADING, LearningPriority.MEDIUM,
            "Market sentiment snapshot", ["sentiment", "symbols"]),
        "trading.anomaly.snapshot": EventDefinition("trading.anomaly.snapshot", EventCategory.TRADING, LearningPriority.HIGH,
            "Market anomaly detected", ["anomalies"]),
        "trading.arbitrage.snapshot": EventDefinition("trading.arbitrage.snapshot", EventCategory.TRADING, LearningPriority.HIGH,
            "Arbitrage opportunity snapshot", ["opportunities"]),
    }
    
    # ========== MINING EVENTS ==========
    MINING_EVENTS = {
        # Core mining
        "mining.start": EventDefinition("mining.start", EventCategory.MINING, LearningPriority.HIGH,
            "Mining started", ["coin", "pool", "mode"]),
        "mining.stop": EventDefinition("mining.stop", EventCategory.MINING, LearningPriority.HIGH,
            "Mining stopped", ["reason"]),
        "mining.started": EventDefinition("mining.started", EventCategory.MINING, LearningPriority.HIGH,
            "Mining has started", ["coin", "hashrate"]),
        "mining.stopped": EventDefinition("mining.stopped", EventCategory.MINING, LearningPriority.HIGH,
            "Mining has stopped", ["coin"]),
            
        # Stats and performance
        "mining.stats.update": EventDefinition("mining.stats.update", EventCategory.MINING, LearningPriority.MEDIUM,
            "Mining statistics update", ["hashrate", "shares", "power"]),
        "mining.status_update": EventDefinition("mining.status_update", EventCategory.MINING, LearningPriority.MEDIUM,
            "Mining status update", ["status", "active"]),
        "mining.hashrate_update": EventDefinition("mining.hashrate_update", EventCategory.MINING, LearningPriority.MEDIUM,
            "Hashrate update", ["hashrate", "unit"]),
            
        # Intelligence (SOTA 2026 - Critical for MiningIntelligence)
        "mining.difficulty_update": EventDefinition("mining.difficulty_update", EventCategory.MINING, LearningPriority.HIGH,
            "Mining difficulty changed", ["difficulty", "change_pct"]),
        "mining.reward_update": EventDefinition("mining.reward_update", EventCategory.MINING, LearningPriority.HIGH,
            "Mining reward update", ["shares_accepted", "estimated_reward"]),
        "mining.algorithm_performance": EventDefinition("mining.algorithm_performance", EventCategory.MINING, LearningPriority.HIGH,
            "Algorithm performance metrics", ["algorithm", "hashrate", "efficiency"]),
        "mining.intelligence.update": EventDefinition("mining.intelligence.update", EventCategory.MINING, LearningPriority.HIGH,
            "Mining intelligence update", ["recommendations", "predictions"]),
        "mining.intelligence.recommendation": EventDefinition("mining.intelligence.recommendation", EventCategory.MINING, LearningPriority.HIGH,
            "Mining recommendation", ["action", "reason", "expected_improvement"]),
            
        # Pool management
        "mining.pool.add": EventDefinition("mining.pool.add", EventCategory.MINING, LearningPriority.MEDIUM,
            "Mining pool added", ["pool", "coin"]),
        "mining.pool.switch": EventDefinition("mining.pool.switch", EventCategory.MINING, LearningPriority.HIGH,
            "Mining pool switched", ["from_pool", "to_pool", "reason"]),
        "mining.algorithm_switch": EventDefinition("mining.algorithm_switch", EventCategory.MINING, LearningPriority.HIGH,
            "Mining algorithm switched", ["from_algo", "to_algo"]),
    }
    
    # ========== MARKET EVENTS ==========
    MARKET_EVENTS = {
        "market.data": EventDefinition("market.data", EventCategory.MARKET, LearningPriority.MEDIUM,
            "Market data update", ["symbol", "price", "volume"]),
        "market.data.update": EventDefinition("market.data.update", EventCategory.MARKET, LearningPriority.MEDIUM,
            "Market data update", ["data"]),
        "market.price_update": EventDefinition("market.price_update", EventCategory.MARKET, LearningPriority.MEDIUM,
            "Price update (MiningIntelligence)", ["symbol", "price", "change_24h"]),
        "market.prices_update": EventDefinition("market.prices_update", EventCategory.MARKET, LearningPriority.MEDIUM,
            "Prices update (legacy)", ["prices"]),
        "market.trend_update": EventDefinition("market.trend_update", EventCategory.MARKET, LearningPriority.HIGH,
            "Market trend update (MiningIntelligence)", ["symbol", "trend", "change_24h"]),
        "market.update": EventDefinition("market.update", EventCategory.MARKET, LearningPriority.MEDIUM,
            "Market update (legacy)", ["data"]),
        "market.status": EventDefinition("market.status", EventCategory.MARKET, LearningPriority.LOW,
            "Market status", ["status", "exchanges"]),
        "market.sentiment": EventDefinition("market.sentiment", EventCategory.MARKET, LearningPriority.HIGH,
            "Market sentiment", ["sentiment", "fear_greed"]),
        "market.liquidity": EventDefinition("market.liquidity", EventCategory.MARKET, LearningPriority.MEDIUM,
            "Market liquidity", ["symbol", "bid_depth", "ask_depth"]),
    }
    
    # ========== BLOCKCHAIN EVENTS ==========
    BLOCKCHAIN_EVENTS = {
        "blockchain.block.new": EventDefinition("blockchain.block.new", EventCategory.BLOCKCHAIN, LearningPriority.HIGH,
            "New block detected", ["block_number", "chain"]),
        "blockchain.transaction_recorded": EventDefinition("blockchain.transaction_recorded", EventCategory.BLOCKCHAIN, LearningPriority.HIGH,
            "Transaction recorded", ["tx_hash", "status"]),
        "blockchain.gas.update": EventDefinition("blockchain.gas.update", EventCategory.BLOCKCHAIN, LearningPriority.MEDIUM,
            "Gas price update", ["gas_price", "chain"]),
        "blockchain.whale_transaction": EventDefinition("blockchain.whale_transaction", EventCategory.BLOCKCHAIN, LearningPriority.CRITICAL,
            "Whale transaction detected", ["tx_hash", "amount", "from", "to"]),
        "blockchain.status": EventDefinition("blockchain.status", EventCategory.BLOCKCHAIN, LearningPriority.LOW,
            "Blockchain status", ["chain", "status"]),
    }
    
    # ========== VOICE EVENTS ==========
    VOICE_EVENTS = {
        "voice.speak": EventDefinition("voice.speak", EventCategory.VOICE, LearningPriority.MEDIUM,
            "Voice speak request", ["text", "voice"]),
        "voice.speak.request": EventDefinition("voice.speak.request", EventCategory.VOICE, LearningPriority.MEDIUM,
            "Voice speak request", ["text", "voice", "source"]),
        "voice.speaking.started": EventDefinition("voice.speaking.started", EventCategory.VOICE, LearningPriority.LOW,
            "Voice started speaking", ["text"]),
        "voice.speaking.stopped": EventDefinition("voice.speaking.stopped", EventCategory.VOICE, LearningPriority.LOW,
            "Voice stopped speaking", []),
        "voice.listen": EventDefinition("voice.listen", EventCategory.VOICE, LearningPriority.MEDIUM,
            "Voice listen request", ["duration"]),
        "voice.listen.request": EventDefinition("voice.listen.request", EventCategory.VOICE, LearningPriority.MEDIUM,
            "Voice listen request", ["duration", "source"]),
        "voice.recognition.start": EventDefinition("voice.recognition.start", EventCategory.VOICE, LearningPriority.MEDIUM,
            "Voice recognition started", []),
        "voice.command_result": EventDefinition("voice.command_result", EventCategory.VOICE, LearningPriority.HIGH,
            "Voice command result", ["command", "success", "response"]),
        "voice.error": EventDefinition("voice.error", EventCategory.VOICE, LearningPriority.HIGH,
            "Voice error", ["error"]),
        "voice.status": EventDefinition("voice.status", EventCategory.VOICE, LearningPriority.LOW,
            "Voice system status", ["status", "listening", "speaking"]),
    }
    
    # ========== VR EVENTS ==========
    VR_EVENTS = {
        "vr.started": EventDefinition("vr.started", EventCategory.VR, LearningPriority.MEDIUM,
            "VR session started", []),
        "vr.stopped": EventDefinition("vr.stopped", EventCategory.VR, LearningPriority.MEDIUM,
            "VR session stopped", []),
        "vr.status": EventDefinition("vr.status", EventCategory.VR, LearningPriority.LOW,
            "VR status", ["status", "device"]),
        "vr.device.connected": EventDefinition("vr.device.connected", EventCategory.VR, LearningPriority.HIGH,
            "VR device connected", ["device", "type"]),
        "vr.device.disconnected": EventDefinition("vr.device.disconnected", EventCategory.VR, LearningPriority.HIGH,
            "VR device disconnected", ["device"]),
        "vr.scene.updated": EventDefinition("vr.scene.updated", EventCategory.VR, LearningPriority.LOW,
            "VR scene updated", ["scene", "changes"]),
        "vr.interaction": EventDefinition("vr.interaction", EventCategory.VR, LearningPriority.MEDIUM,
            "VR interaction event", ["type", "target"]),
        "vr.tracking.update": EventDefinition("vr.tracking.update", EventCategory.VR, LearningPriority.LOW,
            "VR tracking update", ["position", "rotation"]),
        "vr.environment.changed": EventDefinition("vr.environment.changed", EventCategory.VR, LearningPriority.MEDIUM,
            "VR environment changed", ["environment"]),
        
        # SOTA 2026: VR-Genie3 Integration
        "vr.genie3.connected": EventDefinition("vr.genie3.connected", EventCategory.VR, LearningPriority.HIGH,
            "Genie 3 connected to VR", ["status", "initialized"]),
        "vr.world.generating": EventDefinition("vr.world.generating", EventCategory.VR, LearningPriority.MEDIUM,
            "VR world generation started", ["prompt", "world_type"]),
        "vr.world.ready": EventDefinition("vr.world.ready", EventCategory.VR, LearningPriority.HIGH,
            "VR world ready", ["world_id", "prompt", "frame_count"]),
        "vr.world.loaded": EventDefinition("vr.world.loaded", EventCategory.VR, LearningPriority.MEDIUM,
            "VR world loaded", ["world_id", "ready_for_rendering"]),
        "vr.world.stepped": EventDefinition("vr.world.stepped", EventCategory.VR, LearningPriority.LOW,
            "VR world stepped", ["world_id", "action", "frame_index"]),
        "vr.world.frame_update": EventDefinition("vr.world.frame_update", EventCategory.VR, LearningPriority.LOW,
            "VR world frame update", ["world_id", "frame_index"]),
        "vr.world.exported": EventDefinition("vr.world.exported", EventCategory.VR, LearningPriority.MEDIUM,
            "VR world exported", ["world_id", "format", "path"]),
        "vr.world.error": EventDefinition("vr.world.error", EventCategory.VR, LearningPriority.HIGH,
            "VR world error", ["error", "prompt"]),
        
        # SOTA 2026: VR-Creation Engine Integration
        "vr.creation_engine.connected": EventDefinition("vr.creation_engine.connected", EventCategory.VR, LearningPriority.MEDIUM,
            "Creation Engine connected to VR", ["status", "host", "port"]),
        "vr.creation.requested": EventDefinition("vr.creation.requested", EventCategory.VR, LearningPriority.MEDIUM,
            "VR creation requested", ["request_id", "prompt", "mode"]),
        "vr.creation.progress": EventDefinition("vr.creation.progress", EventCategory.VR, LearningPriority.LOW,
            "VR creation progress", ["request_id", "progress", "status"]),
        "vr.creation.complete": EventDefinition("vr.creation.complete", EventCategory.VR, LearningPriority.HIGH,
            "VR creation complete", ["request_id", "status", "image_path"]),
        "vr.creation.error": EventDefinition("vr.creation.error", EventCategory.VR, LearningPriority.HIGH,
            "VR creation error", ["error", "prompt"]),
        
        # SOTA 2026: VR-Vision Integration
        "vr.vision.status": EventDefinition("vr.vision.status", EventCategory.VR, LearningPriority.LOW,
            "VR vision status", ["vision_active", "vision_url"]),
        "vr.vision.processing": EventDefinition("vr.vision.processing", EventCategory.VR, LearningPriority.LOW,
            "VR processing vision frame", ["timestamp", "for_world_generation"]),
        "vr.vision_to_world.status": EventDefinition("vr.vision_to_world.status", EventCategory.VR, LearningPriority.MEDIUM,
            "Vision to world mode status", ["enabled"]),
    }
    
    # ========== VISION STREAM EVENTS ==========
    VISION_EVENTS = {
        "vision.stream.start": EventDefinition("vision.stream.start", EventCategory.VR, LearningPriority.MEDIUM,
            "Vision stream start request", ["url"]),
        "vision.stream.stop": EventDefinition("vision.stream.stop", EventCategory.VR, LearningPriority.MEDIUM,
            "Vision stream stop request", []),
        "vision.stream.status": EventDefinition("vision.stream.status", EventCategory.VR, LearningPriority.LOW,
            "Vision stream status", ["active", "url", "error"]),
        "vision.stream.frame": EventDefinition("vision.stream.frame", EventCategory.VR, LearningPriority.LOW,
            "Vision stream frame", ["frame", "timestamp"]),
        
        # SOTA 2026: Vision-Genie3 Integration
        "vision.generate_world": EventDefinition("vision.generate_world", EventCategory.VR, LearningPriority.HIGH,
            "Vision to world generation request", ["prompt", "world_type", "quality"]),
        "vision.world.generating": EventDefinition("vision.world.generating", EventCategory.VR, LearningPriority.MEDIUM,
            "Vision world generation started", ["prompt", "world_type"]),
        "vision.world.ready": EventDefinition("vision.world.ready", EventCategory.VR, LearningPriority.HIGH,
            "Vision world ready", ["world_id", "prompt", "frame_count", "source"]),
        "vision.world.error": EventDefinition("vision.world.error", EventCategory.VR, LearningPriority.HIGH,
            "Vision world error", ["error", "prompt"]),
        "vision.genie3.world_ready": EventDefinition("vision.genie3.world_ready", EventCategory.VR, LearningPriority.HIGH,
            "Vision Genie3 world ready", ["world_id", "success"]),
        
        # SOTA 2026: Vision-Creation Engine Integration
        "vision.create_image": EventDefinition("vision.create_image", EventCategory.VR, LearningPriority.MEDIUM,
            "Vision to image creation request", ["prompt", "mode"]),
        "vision.creation.requested": EventDefinition("vision.creation.requested", EventCategory.VR, LearningPriority.MEDIUM,
            "Vision creation requested", ["request_id", "prompt", "mode"]),
        "vision.creation.complete": EventDefinition("vision.creation.complete", EventCategory.VR, LearningPriority.HIGH,
            "Vision creation complete", ["request_id", "status", "image_path"]),
        
        # SOTA 2026: Vision Frame Capture
        "vision.capture_for_world": EventDefinition("vision.capture_for_world", EventCategory.VR, LearningPriority.MEDIUM,
            "Capture frame for world generation", []),
        "vision.frame.captured": EventDefinition("vision.frame.captured", EventCategory.VR, LearningPriority.MEDIUM,
            "Vision frame captured", ["timestamp", "for_world_generation"]),
    }
    
    # ========== SYSTEM EVENTS ==========
    SYSTEM_EVENTS = {
        "system.status": EventDefinition("system.status", EventCategory.SYSTEM, LearningPriority.LOW,
            "System status", ["status", "components"]),
        "system.ready": EventDefinition("system.ready", EventCategory.SYSTEM, LearningPriority.HIGH,
            "System ready", []),
        "system.shutdown": EventDefinition("system.shutdown", EventCategory.SYSTEM, LearningPriority.CRITICAL,
            "System shutdown", ["reason"]),
        "system.error": EventDefinition("system.error", EventCategory.SYSTEM, LearningPriority.CRITICAL,
            "System error", ["error", "component"]),
        "system.critical_error": EventDefinition("system.critical_error", EventCategory.SYSTEM, LearningPriority.CRITICAL,
            "Critical system error", ["error", "component", "stacktrace"]),
        "system.warning": EventDefinition("system.warning", EventCategory.SYSTEM, LearningPriority.HIGH,
            "System warning", ["warning", "component"]),
        "system.component_status": EventDefinition("system.component_status", EventCategory.SYSTEM, LearningPriority.LOW,
            "Component status update", ["component", "status"]),
        "system.resource_status": EventDefinition("system.resource_status", EventCategory.SYSTEM, LearningPriority.MEDIUM,
            "Resource status", ["cpu", "memory", "gpu"]),
        "system.predator_mode_activated": EventDefinition("system.predator_mode_activated", EventCategory.SYSTEM, LearningPriority.CRITICAL,
            "Predator mode activated", []),
    }
    
    # ========== LEARNING EVENTS ==========
    LEARNING_EVENTS = {
        "learning.metrics": EventDefinition("learning.metrics", EventCategory.LEARNING, LearningPriority.HIGH,
            "Learning metrics update", ["metrics", "period"]),
        "learning.readiness": EventDefinition("learning.readiness", EventCategory.LEARNING, LearningPriority.HIGH,
            "Learning readiness status", ["ready", "progress"]),
        "learning.pattern": EventDefinition("learning.pattern", EventCategory.LEARNING, LearningPriority.HIGH,
            "Pattern learned", ["pattern", "confidence"]),
        "learning.insight": EventDefinition("learning.insight", EventCategory.LEARNING, LearningPriority.HIGH,
            "Insight generated", ["insight", "source"]),
        "learning.fact_learned": EventDefinition("learning.fact_learned", EventCategory.LEARNING, LearningPriority.MEDIUM,
            "Fact learned", ["fact", "confidence"]),
        "learning.knowledge_synthesized": EventDefinition("learning.knowledge_synthesized", EventCategory.LEARNING, LearningPriority.HIGH,
            "Knowledge synthesized", ["knowledge", "sources"]),
        "learning.processed": EventDefinition("learning.processed", EventCategory.LEARNING, LearningPriority.MEDIUM,
            "Learning processed", ["task_type", "model", "duration"]),
    }
    
    # ========== THOTH EVENTS ==========
    THOTH_EVENTS = {
        "thoth.query": EventDefinition("thoth.query", EventCategory.THOTH, LearningPriority.HIGH,
            "Thoth query", ["query", "context"]),
        "thoth.request": EventDefinition("thoth.request", EventCategory.THOTH, LearningPriority.HIGH,
            "Thoth request", ["message", "user"]),
        "thoth.message": EventDefinition("thoth.message", EventCategory.THOTH, LearningPriority.HIGH,
            "Thoth message", ["message", "role"]),
        "thoth.thinking": EventDefinition("thoth.thinking", EventCategory.THOTH, LearningPriority.MEDIUM,
            "Thoth thinking indicator", ["thinking"]),
        "thoth.status": EventDefinition("thoth.status", EventCategory.THOTH, LearningPriority.LOW,
            "Thoth status", ["status"]),
        "thoth.model_changed": EventDefinition("thoth.model_changed", EventCategory.THOTH, LearningPriority.MEDIUM,
            "Thoth model changed", ["model"]),
        "thoth.voice.command": EventDefinition("thoth.voice.command", EventCategory.THOTH, LearningPriority.HIGH,
            "Thoth voice command", ["command"]),
        "thoth.voice.speak": EventDefinition("thoth.voice.speak", EventCategory.THOTH, LearningPriority.MEDIUM,
            "Thoth speaking", ["text"]),
    }
    
    # ========== BRAIN EVENTS ==========
    BRAIN_EVENTS = {
        "brain.request": EventDefinition("brain.request", EventCategory.AI, LearningPriority.HIGH,
            "Brain request", ["prompt", "domain", "context"]),
        "brain.response": EventDefinition("brain.response", EventCategory.AI, LearningPriority.HIGH,
            "Brain response", ["response", "model"]),
        "brain.error": EventDefinition("brain.error", EventCategory.AI, LearningPriority.CRITICAL,
            "Brain error", ["error"]),
        "brain.metrics": EventDefinition("brain.metrics", EventCategory.AI, LearningPriority.MEDIUM,
            "Brain metrics", ["metrics"]),
        "brain.progress": EventDefinition("brain.progress", EventCategory.AI, LearningPriority.LOW,
            "Brain progress", ["progress"]),
        "brain.visual.request": EventDefinition("brain.visual.request", EventCategory.AI, LearningPriority.HIGH,
            "Brain visual request", ["prompt", "type"]),
        "brain.context.update": EventDefinition("brain.context.update", EventCategory.AI, LearningPriority.MEDIUM,
            "Brain context update", ["context"]),
    }
    
    # ========== SENTIENCE EVENTS ==========
    SENTIENCE_EVENTS = {
        "sentience.detection": EventDefinition("sentience.detection", EventCategory.SENTIENCE, LearningPriority.CRITICAL,
            "Sentience detection", ["level", "components"]),
        "sentience.threshold.crossed": EventDefinition("sentience.threshold.crossed", EventCategory.SENTIENCE, LearningPriority.CRITICAL,
            "Sentience threshold crossed", ["threshold", "direction"]),
        "trading.sentience.update": EventDefinition("trading.sentience.update", EventCategory.SENTIENCE, LearningPriority.HIGH,
            "Trading sentience update", ["score", "components"]),
        "trading.sentience.threshold.alert": EventDefinition("trading.sentience.threshold.alert", EventCategory.SENTIENCE, LearningPriority.CRITICAL,
            "Trading sentience alert", ["threshold", "action"]),
    }
    
    # ========== SECURITY EVENTS ==========
    SECURITY_EVENTS = {
        "security.authenticated": EventDefinition("security.authenticated", EventCategory.SECURITY, LearningPriority.HIGH,
            "User authenticated", ["user", "method"]),
        "security.locked": EventDefinition("security.locked", EventCategory.SECURITY, LearningPriority.HIGH,
            "System locked", ["reason"]),
        "security.unlocked": EventDefinition("security.unlocked", EventCategory.SECURITY, LearningPriority.HIGH,
            "System unlocked", ["method"]),
        "security.audit.complete": EventDefinition("security.audit.complete", EventCategory.SECURITY, LearningPriority.HIGH,
            "Security audit complete", ["results"]),
        "security.face.enrolled": EventDefinition("security.face.enrolled", EventCategory.SECURITY, LearningPriority.HIGH,
            "Face enrolled", ["user"]),
        "security.voice.enrolled": EventDefinition("security.voice.enrolled", EventCategory.SECURITY, LearningPriority.HIGH,
            "Voice enrolled", ["user"]),
        "security.boot_scan.started": EventDefinition("security.boot_scan.started", EventCategory.SECURITY, LearningPriority.MEDIUM,
            "Boot scan started", []),
    }
    
    # ========== STRATEGY EVENTS ==========
    STRATEGY_EVENTS = {
        "strategy.signal": EventDefinition("strategy.signal", EventCategory.STRATEGY, LearningPriority.CRITICAL,
            "Strategy signal", ["signal", "symbol", "direction"]),
        "strategy.started": EventDefinition("strategy.started", EventCategory.STRATEGY, LearningPriority.HIGH,
            "Strategy started", ["strategy", "params"]),
        "strategy.stopped": EventDefinition("strategy.stopped", EventCategory.STRATEGY, LearningPriority.HIGH,
            "Strategy stopped", ["strategy", "reason"]),
        "strategy.error": EventDefinition("strategy.error", EventCategory.STRATEGY, LearningPriority.CRITICAL,
            "Strategy error", ["strategy", "error"]),
        "strategy.backtest": EventDefinition("strategy.backtest", EventCategory.STRATEGY, LearningPriority.HIGH,
            "Strategy backtest", ["strategy", "results"]),
        "strategy.updated": EventDefinition("strategy.updated", EventCategory.STRATEGY, LearningPriority.MEDIUM,
            "Strategy updated", ["strategy", "changes"]),
    }
    
    # ========== RISK EVENTS ==========
    RISK_EVENTS = {
        "risk.status": EventDefinition("risk.status", EventCategory.RISK, LearningPriority.HIGH,
            "Risk status", ["status", "metrics"]),
        "risk.metrics.update": EventDefinition("risk.metrics.update", EventCategory.RISK, LearningPriority.HIGH,
            "Risk metrics update", ["metrics"]),
        "risk.assessment.request": EventDefinition("risk.assessment.request", EventCategory.RISK, LearningPriority.HIGH,
            "Risk assessment request", ["portfolio"]),
        "risk.threshold.update": EventDefinition("risk.threshold.update", EventCategory.RISK, LearningPriority.HIGH,
            "Risk threshold update", ["threshold", "new_value"]),
        "trading.risk.snapshot": EventDefinition("trading.risk.snapshot", EventCategory.RISK, LearningPriority.HIGH,
            "Trading risk snapshot", ["snapshot"]),
    }
    
    # ========== VISUAL/CREATIVE EVENTS ==========
    CREATIVE_EVENTS = {
        "visual.generated": EventDefinition("visual.generated", EventCategory.CREATIVE, LearningPriority.HIGH,
            "Visual generated", ["type", "path", "prompt"]),
        "visual.request": EventDefinition("visual.request", EventCategory.CREATIVE, LearningPriority.MEDIUM,
            "Visual request", ["type", "prompt"]),
        "visual.generation.started": EventDefinition("visual.generation.started", EventCategory.CREATIVE, LearningPriority.LOW,
            "Visual generation started", ["type"]),
        "visual.generation.progress": EventDefinition("visual.generation.progress", EventCategory.CREATIVE, LearningPriority.LOW,
            "Visual generation progress", ["progress"]),
        "visual.generation.error": EventDefinition("visual.generation.error", EventCategory.CREATIVE, LearningPriority.HIGH,
            "Visual generation error", ["error"]),
        "creative.create": EventDefinition("creative.create", EventCategory.CREATIVE, LearningPriority.HIGH,
            "Creative creation request", ["type", "params"]),
        "creative.voice.create": EventDefinition("creative.voice.create", EventCategory.CREATIVE, LearningPriority.HIGH,
            "Creative voice request", ["text", "voice"]),
        "image.generated": EventDefinition("image.generated", EventCategory.CREATIVE, LearningPriority.HIGH,
            "Image generated", ["path", "prompt"]),
        "creative.preview.updated": EventDefinition("creative.preview.updated", EventCategory.CREATIVE, LearningPriority.LOW,
            "Creative preview updated", ["preview_type", "timestamp"]),
    }
    
    # ========== VR PORTFOLIO EVENTS ==========
    VR_PORTFOLIO_EVENTS = {
        "vr.portfolio.initialized": EventDefinition("vr.portfolio.initialized", EventCategory.VR, LearningPriority.MEDIUM,
            "VR portfolio view initialized", ["status", "layout"]),
        "vr.portfolio.updated": EventDefinition("vr.portfolio.updated", EventCategory.VR, LearningPriority.MEDIUM,
            "VR portfolio updated", ["position_count", "total_value", "daily_pnl"]),
        "vr.portfolio.position.added": EventDefinition("vr.portfolio.position.added", EventCategory.VR, LearningPriority.MEDIUM,
            "VR portfolio position added", ["symbol", "animation"]),
        "vr.portfolio.position.removed": EventDefinition("vr.portfolio.position.removed", EventCategory.VR, LearningPriority.MEDIUM,
            "VR portfolio position removed", ["symbol", "animation"]),
        "vr.portfolio.position.selected": EventDefinition("vr.portfolio.position.selected", EventCategory.VR, LearningPriority.LOW,
            "VR portfolio position selected", ["symbol", "position", "visual"]),
        "vr.portfolio.error": EventDefinition("vr.portfolio.error", EventCategory.VR, LearningPriority.HIGH,
            "VR portfolio error", ["error", "phase"]),
        "vr.portfolio.cleanup": EventDefinition("vr.portfolio.cleanup", EventCategory.VR, LearningPriority.LOW,
            "VR portfolio cleanup", ["status"]),
    }
    
    # ========== CONTRACT MANAGER EVENTS ==========
    CONTRACT_EVENTS = {
        "contract.manager.initialized": EventDefinition("contract.manager.initialized", EventCategory.TRADING, LearningPriority.MEDIUM,
            "Contract manager initialized", ["status", "supported_types"]),
        "contract.created": EventDefinition("contract.created", EventCategory.TRADING, LearningPriority.HIGH,
            "Contract created", ["contract_id", "type", "status", "value"]),
        "contract.activated": EventDefinition("contract.activated", EventCategory.TRADING, LearningPriority.HIGH,
            "Contract activated", ["contract_id", "type"]),
        "contract.executed": EventDefinition("contract.executed", EventCategory.TRADING, LearningPriority.CRITICAL,
            "Contract executed", ["contract_id", "type", "value", "actions_executed"]),
        "contract.execution.failed": EventDefinition("contract.execution.failed", EventCategory.TRADING, LearningPriority.CRITICAL,
            "Contract execution failed", ["contract_id", "error"]),
        "contract.cancelled": EventDefinition("contract.cancelled", EventCategory.TRADING, LearningPriority.MEDIUM,
            "Contract cancelled", ["contract_id", "reason"]),
        "contract.expired": EventDefinition("contract.expired", EventCategory.TRADING, LearningPriority.MEDIUM,
            "Contract expired", ["contract_id"]),
        "contract.creation.error": EventDefinition("contract.creation.error", EventCategory.TRADING, LearningPriority.HIGH,
            "Contract creation error", ["error", "terms"]),
        "contract.manager.error": EventDefinition("contract.manager.error", EventCategory.TRADING, LearningPriority.HIGH,
            "Contract manager error", ["error", "phase"]),
        "contract.manager.cleanup": EventDefinition("contract.manager.cleanup", EventCategory.TRADING, LearningPriority.LOW,
            "Contract manager cleanup", ["status"]),
    }
    
    # ========== CHART GENERATOR EVENTS ==========
    CHART_EVENTS = {
        "chart.generator.initialized": EventDefinition("chart.generator.initialized", EventCategory.CREATIVE, LearningPriority.MEDIUM,
            "Chart generator initialized", ["status", "supported_types", "supported_indicators"]),
        "chart.created": EventDefinition("chart.created", EventCategory.CREATIVE, LearningPriority.MEDIUM,
            "Chart created", ["chart_id", "symbol", "type"]),
        "chart.updated": EventDefinition("chart.updated", EventCategory.CREATIVE, LearningPriority.LOW,
            "Chart updated", ["chart_id", "candle"]),
        "chart.generated": EventDefinition("chart.generated", EventCategory.CREATIVE, LearningPriority.MEDIUM,
            "Chart generated from request", ["chart_id", "symbol", "render"]),
        "chart.removed": EventDefinition("chart.removed", EventCategory.CREATIVE, LearningPriority.LOW,
            "Chart removed", ["chart_id"]),
        "chart.generator.error": EventDefinition("chart.generator.error", EventCategory.CREATIVE, LearningPriority.HIGH,
            "Chart generator error", ["error", "phase"]),
        "chart.generator.cleanup": EventDefinition("chart.generator.cleanup", EventCategory.CREATIVE, LearningPriority.LOW,
            "Chart generator cleanup", ["status"]),
        "chart.request": EventDefinition("chart.request", EventCategory.CREATIVE, LearningPriority.MEDIUM,
            "Chart generation request", ["symbol", "type", "timeframe"]),
    }
    
    # ========== TRADING INTELLIGENCE EVENTS ==========
    TRADING_INTELLIGENCE_EVENTS = {
        "trading.market_anomalies": EventDefinition("trading.market_anomalies", EventCategory.TRADING, LearningPriority.HIGH,
            "Market anomalies detected", ["symbol", "anomalies", "timestamp"]),
        "trading.anomaly_opportunity": EventDefinition("trading.anomaly_opportunity", EventCategory.TRADING, LearningPriority.CRITICAL,
            "Trading opportunity from anomaly", ["opportunity", "timestamp"]),
    }
    
    # ========== WALLET EVENTS ==========
    WALLET_EVENTS = {
        "wallet.balance.update": EventDefinition("wallet.balance.update", EventCategory.WALLET, LearningPriority.HIGH,
            "Wallet balance update", ["balances"]),
        "portfolio.update": EventDefinition("portfolio.update", EventCategory.WALLET, LearningPriority.HIGH,
            "Portfolio update", ["portfolio"]),
        "portfolio.snapshot": EventDefinition("portfolio.snapshot", EventCategory.WALLET, LearningPriority.HIGH,
            "Portfolio snapshot", ["snapshot"]),
        "collateral_update": EventDefinition("collateral_update", EventCategory.WALLET, LearningPriority.HIGH,
            "Collateral update", ["collateral"]),
    }
    
    # ========== QUANTUM EVENTS ==========
    QUANTUM_EVENTS = {
        "quantum.optimization.complete": EventDefinition("quantum.optimization.complete", EventCategory.QUANTUM, LearningPriority.HIGH,
            "Quantum optimization complete", ["result"]),
        "quantum.mining.started": EventDefinition("quantum.mining.started", EventCategory.QUANTUM, LearningPriority.HIGH,
            "Quantum mining started", []),
        "quantum.mining.stopped": EventDefinition("quantum.mining.stopped", EventCategory.QUANTUM, LearningPriority.HIGH,
            "Quantum mining stopped", []),
        "quantum.trading.enable": EventDefinition("quantum.trading.enable", EventCategory.QUANTUM, LearningPriority.HIGH,
            "Quantum trading enabled", []),
        "quantum.nexus.connected": EventDefinition("quantum.nexus.connected", EventCategory.QUANTUM, LearningPriority.HIGH,
            "Quantum nexus connected", []),
    }
    
    # ========== API EVENTS ==========
    API_EVENTS = {
        "api.request": EventDefinition("api.request", EventCategory.API, LearningPriority.LOW,
            "API request", ["endpoint", "method"]),
        "api.status": EventDefinition("api.status", EventCategory.API, LearningPriority.LOW,
            "API status", ["status"]),
        "api.key.add": EventDefinition("api.key.add", EventCategory.API, LearningPriority.MEDIUM,
            "API key added", ["service"]),
        "api.key.delete": EventDefinition("api.key.delete", EventCategory.API, LearningPriority.MEDIUM,
            "API key deleted", ["service"]),
        "api.test_result": EventDefinition("api.test_result", EventCategory.API, LearningPriority.MEDIUM,
            "API test result", ["service", "success"]),
    }
    
    # ========== COMMS EVENTS ==========
    COMMS_EVENTS = {
        "comms.call.start": EventDefinition("comms.call.start", EventCategory.COMMS, LearningPriority.HIGH,
            "Communication call start", ["type", "target"]),
        "comms.call.stop": EventDefinition("comms.call.stop", EventCategory.COMMS, LearningPriority.HIGH,
            "Communication call stop", []),
        "comms.radio.transmit": EventDefinition("comms.radio.transmit", EventCategory.COMMS, LearningPriority.MEDIUM,
            "Radio transmission", ["frequency", "message"]),
        "comms.sonar.start": EventDefinition("comms.sonar.start", EventCategory.COMMS, LearningPriority.MEDIUM,
            "Sonar started", []),
        "comms.scan": EventDefinition("comms.scan", EventCategory.COMMS, LearningPriority.MEDIUM,
            "Communication scan", ["type"]),
    }
    
    # ========== NAVIGATION EVENTS ==========
    NAVIGATION_EVENTS = {
        "navigate.tab.dashboard": EventDefinition("navigate.tab.dashboard", EventCategory.NAVIGATION, LearningPriority.LOW,
            "Navigate to dashboard", []),
        "navigate.tab.trading": EventDefinition("navigate.tab.trading", EventCategory.NAVIGATION, LearningPriority.LOW,
            "Navigate to trading", []),
        "navigate.tab.mining": EventDefinition("navigate.tab.mining", EventCategory.NAVIGATION, LearningPriority.LOW,
            "Navigate to mining", []),
        "navigate.tab.wallet": EventDefinition("navigate.tab.wallet", EventCategory.NAVIGATION, LearningPriority.LOW,
            "Navigate to wallet", []),
        "navigate.tab.vr": EventDefinition("navigate.tab.vr", EventCategory.NAVIGATION, LearningPriority.LOW,
            "Navigate to VR", []),
        "tab.changed": EventDefinition("tab.changed", EventCategory.NAVIGATION, LearningPriority.LOW,
            "Tab changed", ["tab"]),
    }
    
    # ========== SETTINGS EVENTS ==========
    SETTINGS_EVENTS = {
        "settings.updated": EventDefinition("settings.updated", EventCategory.SETTINGS, LearningPriority.MEDIUM,
            "Settings updated", ["settings"]),
        "settings.saved": EventDefinition("settings.saved", EventCategory.SETTINGS, LearningPriority.MEDIUM,
            "Settings saved", []),
        "settings.theme.changed": EventDefinition("settings.theme.changed", EventCategory.SETTINGS, LearningPriority.LOW,
            "Theme changed", ["theme"]),
        "theme.changed": EventDefinition("theme.changed", EventCategory.SETTINGS, LearningPriority.LOW,
            "Theme changed", ["theme"]),
    }
    
    # ========== COMPONENT EVENTS ==========
    COMPONENT_EVENTS = {
        "component.ready": EventDefinition("component.ready", EventCategory.SYSTEM, LearningPriority.LOW,
            "Component ready", ["component"]),
        "component.failed": EventDefinition("component.failed", EventCategory.SYSTEM, LearningPriority.HIGH,
            "Component failed", ["component", "error"]),
        "component.status": EventDefinition("component.status", EventCategory.SYSTEM, LearningPriority.LOW,
            "Component status", ["component", "status"]),
        "component_registered": EventDefinition("component_registered", EventCategory.SYSTEM, LearningPriority.LOW,
            "Component registered", ["component"]),
    }
    
    # ========== GENIE 3 WORLD MODEL EVENTS (SOTA 2026) ==========
    GENIE3_EVENTS = {
        # Initialization
        "genie3.initialized": EventDefinition("genie3.initialized", EventCategory.CREATIVE, LearningPriority.MEDIUM,
            "Genie 3 world model initialized", ["device", "config"]),
        
        # World generation
        "genie3.generation.started": EventDefinition("genie3.generation.started", EventCategory.CREATIVE, LearningPriority.HIGH,
            "World generation started", ["world_id", "prompt", "world_type"]),
        "genie3.generation.progress": EventDefinition("genie3.generation.progress", EventCategory.CREATIVE, LearningPriority.LOW,
            "World generation progress", ["world_id", "progress", "stage"]),
        "genie3.generation.complete": EventDefinition("genie3.generation.complete", EventCategory.CREATIVE, LearningPriority.HIGH,
            "World generation complete", ["world_id", "success", "frame_count"]),
        "genie3.generation.error": EventDefinition("genie3.generation.error", EventCategory.CREATIVE, LearningPriority.HIGH,
            "World generation error", ["error", "prompt"]),
        
        # World interaction
        "genie3.world.step": EventDefinition("genie3.world.step", EventCategory.CREATIVE, LearningPriority.LOW,
            "World stepped with action", ["world_id", "action", "frame_index"]),
        "genie3.world.state": EventDefinition("genie3.world.state", EventCategory.CREATIVE, LearningPriority.LOW,
            "World state update", ["world_id", "position", "rotation"]),
        
        # Export
        "genie3.export.started": EventDefinition("genie3.export.started", EventCategory.CREATIVE, LearningPriority.MEDIUM,
            "World export started", ["world_id", "format"]),
        "genie3.export.complete": EventDefinition("genie3.export.complete", EventCategory.CREATIVE, LearningPriority.MEDIUM,
            "World export complete", ["world_id", "format", "path"]),
        
        # Memory
        "genie3.memory.update": EventDefinition("genie3.memory.update", EventCategory.CREATIVE, LearningPriority.LOW,
            "World memory updated", ["world_id", "memory_level", "frame_index"]),
        
        # Tokenizer
        "genie3.tokenizer.encode": EventDefinition("genie3.tokenizer.encode", EventCategory.CREATIVE, LearningPriority.LOW,
            "Video encoded to tokens", ["world_id", "token_count"]),
        "genie3.tokenizer.decode": EventDefinition("genie3.tokenizer.decode", EventCategory.CREATIVE, LearningPriority.LOW,
            "Tokens decoded to video", ["world_id", "frame_count"]),
        
        # Dynamics
        "genie3.dynamics.predict": EventDefinition("genie3.dynamics.predict", EventCategory.CREATIVE, LearningPriority.LOW,
            "Next frame predicted", ["world_id", "action", "latency_ms"]),
    }

    @classmethod
    def get_all_events(cls) -> Dict[str, EventDefinition]:
        """Get all events in the catalog."""
        all_events = {}
        all_events.update(cls.AI_EVENTS)
        all_events.update(cls.TRADING_EVENTS)
        all_events.update(cls.MINING_EVENTS)
        all_events.update(cls.MARKET_EVENTS)
        all_events.update(cls.BLOCKCHAIN_EVENTS)
        all_events.update(cls.VOICE_EVENTS)
        all_events.update(cls.VR_EVENTS)
        all_events.update(cls.VISION_EVENTS)
        all_events.update(cls.SYSTEM_EVENTS)
        all_events.update(cls.LEARNING_EVENTS)
        all_events.update(cls.THOTH_EVENTS)
        all_events.update(cls.BRAIN_EVENTS)
        all_events.update(cls.SENTIENCE_EVENTS)
        all_events.update(cls.SECURITY_EVENTS)
        all_events.update(cls.STRATEGY_EVENTS)
        all_events.update(cls.RISK_EVENTS)
        all_events.update(cls.CREATIVE_EVENTS)
        all_events.update(cls.VR_PORTFOLIO_EVENTS)  # SOTA 2026 VR Portfolio
        all_events.update(cls.CONTRACT_EVENTS)  # SOTA 2026 Contract Manager
        all_events.update(cls.CHART_EVENTS)  # SOTA 2026 Chart Generator
        all_events.update(cls.TRADING_INTELLIGENCE_EVENTS)  # SOTA 2026 Anomaly Detection
        all_events.update(cls.WALLET_EVENTS)
        all_events.update(cls.QUANTUM_EVENTS)
        all_events.update(cls.API_EVENTS)
        all_events.update(cls.COMMS_EVENTS)
        all_events.update(cls.NAVIGATION_EVENTS)
        all_events.update(cls.SETTINGS_EVENTS)
        all_events.update(cls.COMPONENT_EVENTS)
        all_events.update(cls.GENIE3_EVENTS)  # SOTA 2026 World Model
        return all_events
    
    @classmethod
    def get_events_by_category(cls, category: EventCategory) -> Dict[str, EventDefinition]:
        """Get all events for a specific category."""
        all_events = cls.get_all_events()
        return {k: v for k, v in all_events.items() if v.category == category}
    
    @classmethod
    def get_learnable_events(cls, min_priority: LearningPriority = LearningPriority.MEDIUM) -> Dict[str, EventDefinition]:
        """Get events that should be learned from (above minimum priority)."""
        all_events = cls.get_all_events()
        return {k: v for k, v in all_events.items() if v.learning_priority.value >= min_priority.value}
    
    @classmethod
    def get_critical_events(cls) -> Dict[str, EventDefinition]:
        """Get critical events that must always be learned from."""
        return cls.get_learnable_events(LearningPriority.CRITICAL)
    
    @classmethod
    def get_event_names_for_subscription(cls, categories: Optional[List[EventCategory]] = None,
                                         min_priority: LearningPriority = LearningPriority.LOW) -> List[str]:
        """Get list of event names to subscribe to for learning."""
        all_events = cls.get_all_events()
        event_names = []
        
        for name, definition in all_events.items():
            if definition.learning_priority.value >= min_priority.value:
                if categories is None or definition.category in categories:
                    event_names.append(name)
        
        return sorted(event_names)
    
    @classmethod
    def get_system_context_for_ai(cls) -> Dict[str, Any]:
        """
        Get a summary of all events for AI system context.
        This helps the Brain/Ollama understand the full system.
        """
        all_events = cls.get_all_events()
        
        context = {
            "total_events": len(all_events),
            "categories": {},
            "critical_events": [],
            "high_priority_events": []
        }
        
        # Organize by category
        for name, definition in all_events.items():
            cat = definition.category.value
            if cat not in context["categories"]:
                context["categories"][cat] = []
            context["categories"][cat].append(name)
            
            if definition.learning_priority == LearningPriority.CRITICAL:
                context["critical_events"].append(name)
            elif definition.learning_priority == LearningPriority.HIGH:
                context["high_priority_events"].append(name)
        
        # Add counts per category
        context["events_per_category"] = {cat: len(events) for cat, events in context["categories"].items()}
        
        return context
    
    @classmethod
    def describe_event(cls, event_name: str) -> str:
        """Get a human-readable description of an event."""
        all_events = cls.get_all_events()
        if event_name in all_events:
            defn = all_events[event_name]
            return f"{defn.name} ({defn.category.value}): {defn.description}"
        return f"Unknown event: {event_name}"


# Singleton instance
EVENT_CATALOG = KingdomEventCatalog()


def get_event_catalog() -> KingdomEventCatalog:
    """Get the global event catalog instance."""
    return EVENT_CATALOG
