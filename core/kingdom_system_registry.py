#!/usr/bin/env python3
"""
Kingdom AI — Unified System Registry
====================================

SINGLE SOURCE OF TRUTH for every component, engine, and capability in the
Kingdom AI system. Every subsystem registers here with:

  - canonical name
  - category            (creation, trading, blockchain, mining, voice, vr,
                         health, security, memory, ai, system, hardware, etc.)
  - natural-language triggers (keywords & phrases the Ollama brain matches)
  - event topics        (request / response / progress)
  - public actions      (method names available on the instance)
  - instance            (live object reference when registered at runtime)
  - file path           (source location for introspection)

Purpose:
  * Ollama brain / BrainRouter / UnifiedBrainRouter knows every tool available
  * Chat widgets and natural-language handlers route to the right engine
  * No module is "hidden" — every tab and every engine is discoverable
  * Eliminates confusion between old and new files: one name → one handler

This registry is also broadcast on the event bus under `system.registry.update`
whenever a component registers so every listener stays in sync.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("KingdomAI.SystemRegistry")


# ──────────────────────────────────────────────────────────────────────
# Categories
# ──────────────────────────────────────────────────────────────────────

class Category(str, Enum):
    CREATION = "creation"
    TRADING = "trading"
    BLOCKCHAIN = "blockchain"
    MINING = "mining"
    VOICE = "voice"
    VR = "vr"
    HEALTH = "health"
    SECURITY = "security"
    MEMORY = "memory"
    AI = "ai"                # Ollama brain, routers, orchestrators
    HARDWARE = "hardware"
    SCIENCE = "science"      # chemistry, biology, metallurgy, physics
    ENGINEERING = "engineering"  # CAD, PCB, manufacturing
    MEDIA = "media"          # music, audio, video playback
    SYSTEM = "system"        # event bus, loaders, infra


# ──────────────────────────────────────────────────────────────────────
# Capability record
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Capability:
    """Description of one capability exposed by a registered component."""
    name: str                                    # canonical, unique
    category: Category
    description: str
    triggers: List[str] = field(default_factory=list)   # NL keywords/phrases
    event_topics_in: List[str] = field(default_factory=list)
    event_topics_out: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)    # public method names
    file_path: Optional[str] = None
    instance: Optional[Any] = field(default=None, repr=False)
    tags: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["tags"] = sorted(self.tags)
        d.pop("instance", None)
        return d


# ──────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────

class KingdomSystemRegistry:
    """
    Thread-safe registry of every Kingdom AI capability.

    Built-in catalog is seeded on first use; live instances can be attached
    via `attach_instance(name, obj)` once the main application boots them.
    """

    _lock = threading.RLock()

    def __init__(self, event_bus: Any = None):
        self._caps: Dict[str, Capability] = {}
        self._by_category: Dict[Category, Set[str]] = {c: set() for c in Category}
        self._by_topic: Dict[str, Set[str]] = {}
        self._by_trigger: Dict[str, Set[str]] = {}
        self.event_bus = event_bus
        self._seed_builtin()

    # ------------------------------------------------------------------ register
    def register(self, cap: Capability) -> None:
        with self._lock:
            self._caps[cap.name] = cap
            self._by_category[cap.category].add(cap.name)
            for t in cap.event_topics_in + cap.event_topics_out:
                self._by_topic.setdefault(t, set()).add(cap.name)
            for trig in cap.triggers:
                self._by_trigger.setdefault(trig.lower(), set()).add(cap.name)
        self._broadcast("register", cap.name)
        logger.debug("Registered capability %s [%s]", cap.name, cap.category.value)

    def attach_instance(self, name: str, instance: Any) -> bool:
        """Bind a live object to a previously-seeded capability."""
        with self._lock:
            cap = self._caps.get(name)
            if cap is None:
                logger.warning("attach_instance: no capability named %r", name)
                return False
            cap.instance = instance
        self._broadcast("attach", name)
        return True

    # ------------------------------------------------------------------ lookup
    def get(self, name: str) -> Optional[Capability]:
        return self._caps.get(name)

    def all(self) -> List[Capability]:
        return list(self._caps.values())

    def by_category(self, category: Category) -> List[Capability]:
        return [self._caps[n] for n in sorted(self._by_category.get(category, []))]

    _STOPWORDS: Set[str] = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "and", "or", "of", "for", "to", "in", "on", "with", "by", "at", "from",
        "into", "about", "as", "this", "that", "these", "those", "it", "its",
        "me", "my", "us", "our", "you", "your", "he", "she", "they", "them",
        "some", "any", "all", "every", "each", "between", "through",
        "please", "now", "then", "up", "down", "out", "off",
        "i", "we", "run",
    }

    def search(self, query: str) -> List[Capability]:
        """Rank capabilities whose triggers/name/description match the query.

        Uses a weighted scoring model:
          +5 exact trigger match
          +3 token is contained in a multi-word trigger
          +3 token matches capability name
          +1 token matches description word
        Stopwords are filtered. Very short tokens (<3 chars) only score against
        exact trigger matches.
        """
        q = query.lower().strip()
        if not q:
            return []
        raw = q.replace(",", " ").replace("/", " ").replace("-", " ").split()
        tokens = [t for t in raw if t and t not in self._STOPWORDS]
        if not tokens:
            return []

        scored: List[tuple[float, Capability]] = []
        for cap in self._caps.values():
            score = 0.0
            name_l = cap.name.lower()
            desc_words = set(cap.description.lower().split())
            trig_lower = [t.lower() for t in cap.triggers]
            for tok in tokens:
                short = len(tok) < 3
                # exact trigger match
                for trig in trig_lower:
                    if tok == trig:
                        score += 5.0
                        break
                else:
                    # multi-word trigger substring
                    for trig in trig_lower:
                        if " " in trig and tok in trig.split():
                            score += 3.0
                            break
                if short:
                    continue
                if tok in name_l:
                    score += 3.0
                if tok in desc_words:
                    score += 1.0
            if score > 0:
                scored.append((score, cap))
        scored.sort(key=lambda x: (x[0], x[1].name), reverse=True)
        return [c for _, c in scored]

    # ------------------------------------------------------------------ export
    def manifest(self) -> Dict[str, Any]:
        """Machine-readable manifest for the Ollama brain to consume."""
        return {
            "total": len(self._caps),
            "by_category": {
                c.value: [self._caps[n].to_dict()
                          for n in sorted(self._by_category[c])]
                for c in Category
            },
            "topics": {t: sorted(names) for t, names in self._by_topic.items()},
        }

    def summary_for_prompt(self) -> str:
        """Compact text summary embeddable in an Ollama system prompt."""
        lines = ["Kingdom AI — available tools:"]
        for c in Category:
            names = sorted(self._by_category[c])
            if not names:
                continue
            lines.append(f"  [{c.value}]")
            for n in names:
                cap = self._caps[n]
                trg = ", ".join(cap.triggers[:4]) if cap.triggers else "-"
                lines.append(f"    - {n}: {cap.description}  (triggers: {trg})")
        return "\n".join(lines)

    # ------------------------------------------------------------------ internal
    def _broadcast(self, action: str, name: str) -> None:
        if not self.event_bus:
            return
        try:
            self.event_bus.publish("system.registry.update", {
                "action": action, "name": name, "total": len(self._caps),
            })
        except Exception:
            pass

    def _add(self, **kwargs) -> None:
        cat = kwargs.pop("category")
        if isinstance(cat, str):
            cat = Category(cat)
        self.register(Capability(category=cat, **kwargs))

    # ------------------------------------------------------------------ catalog
    def _seed_builtin(self) -> None:
        """Seed the registry with every known module.

        Each entry mirrors an actual file on disk. If a module isn't
        present at runtime, the entry stays (as a descriptor) but its
        `instance` is None — callers should guard.
        """
        # ---- CREATION -------------------------------------------------
        self._add(name="visual_creation_canvas", category=Category.CREATION,
                  description="Image/video generation (FLUX, SD3.5, LCM) + video backends",
                  triggers=["image", "picture", "photo", "draw", "paint", "render",
                            "illustrate", "artwork", "generate image", "create image",
                            "video", "clip", "movie"],
                  event_topics_in=["brain.visual.request", "visual.request"],
                  event_topics_out=["visual.generated", "creation.progress", "creation.response"],
                  actions=["create", "generate_from_prompt", "generate_video_from_prompt"],
                  file_path="gui/widgets/visual_creation_canvas.py")

        self._add(name="cinema_engine", category=Category.CREATION,
                  description="Multi-shot cinematic video rendering",
                  triggers=["cinema", "cinematic", "film", "movie", "scene",
                            "shot", "render video"],
                  actions=["generate", "render_video"],
                  file_path="core/cinema_engine_sota_2026.py")

        self._add(name="universal_animation", category=Category.CREATION,
                  description="Motion, particles, physics animation",
                  triggers=["animate", "animation", "motion", "particles", "fx"],
                  actions=["generate"],
                  file_path="core/universal_animation_engine.py")

        self._add(name="medical_reconstruction", category=Category.CREATION,
                  description="CT/MRI → 3D anatomical reconstruction",
                  triggers=["medical 3d", "ct scan", "mri", "anatomy 3d", "reconstruct 3d"],
                  actions=["reconstruct_3d"],
                  file_path="core/medical_reconstruction_engine.py")

        self._add(name="genie3_world", category=Category.CREATION,
                  description="Text → 3D walkable world (Genie3)",
                  triggers=["world", "terrain", "walkable world", "3d world", "environment"],
                  actions=["generate_world"],
                  file_path="core/genie3_world_model.py")

        self._add(name="unified_creative_engine", category=Category.CREATION,
                  description="Maps, dungeons, cities, Unity export, live edit",
                  triggers=["map", "dungeon", "city", "region", "atlas", "unity export"],
                  actions=["create", "generate_map", "render_map_to_image",
                           "export_to_unity", "edit_live", "list_capabilities"],
                  file_path="core/unified_creative_engine.py")

        self._add(name="screenplay_narrative", category=Category.CREATION,
                  description="Screenplays, scripts, narrative structure",
                  triggers=["screenplay", "script", "story", "narrative", "plot"],
                  actions=["generate_screenplay"],
                  file_path="core/screenplay_narrative_engine.py")

        self._add(name="storyboard", category=Category.CREATION,
                  description="Shot planning + animatics",
                  triggers=["storyboard", "shots", "animatic", "breakdown",
                            "short film", "film shots"],
                  actions=["plan_storyboard", "generate_animatic"],
                  file_path="core/storyboard_planner.py")

        self._add(name="character_consistency", category=Category.CREATION,
                  description="Character sheets + visual consistency across shots",
                  triggers=["character", "protagonist", "character sheet"],
                  actions=["create_character"],
                  file_path="core/character_consistency_engine.py")

        self._add(name="cad_mechanical", category=Category.ENGINEERING,
                  description="CAD, STL, G-code, laser, blueprints",
                  triggers=["cad", "mechanical", "stl", "gcode", "3d print",
                            "blueprint", "laser", "engrave"],
                  actions=["generate_from_text", "export_stl",
                           "generate_gcode_fdm", "generate_gcode_laser",
                           "generate_blueprint_dxf", "generate_schematic_svg"],
                  file_path="core/cad_mechanical_engineering_engine.py")

        self._add(name="electronics_circuit", category=Category.ENGINEERING,
                  description="Schematic + PCB + Gerber + manufacturing prep",
                  triggers=["pcb", "circuit", "schematic", "gerber", "electronics"],
                  actions=["generate_circuit", "generate_gerber_files"],
                  file_path="core/electronics_circuit_design_engine.py")

        self._add(name="fashion_clothing", category=Category.CREATION,
                  description="Garment patterns + 3D clothing",
                  triggers=["fashion", "clothing", "garment", "apparel", "dress", "shirt"],
                  actions=["generate_pattern", "generate_3d_garment"],
                  file_path="core/fashion_clothing_design_engine.py")

        self._add(name="architectural_design", category=Category.ENGINEERING,
                  description="Floor plans + architectural layouts",
                  triggers=["architecture", "architectural", "floor plan",
                            "floor", "building", "house", "home design",
                            "bedroom", "room"],
                  actions=["generate_floor_plan"],
                  file_path="core/architectural_design_engine.py")

        self._add(name="industrial_product", category=Category.ENGINEERING,
                  description="Materials selection + product concepts",
                  triggers=["product design", "material", "industrial design"],
                  actions=["recommend_material"],
                  file_path="core/industrial_product_design_engine.py")

        self._add(name="code_generator", category=Category.CREATION,
                  description="Code generation (Python, JS, TS, ...) via Ollama/Thoth",
                  triggers=["code", "script", "function", "class", "write code",
                            "generate code", "program"],
                  event_topics_out=["thoth:code:generate", "REQUEST_CLAW_CODING_TASK"],
                  actions=["generate"],
                  file_path="core/code_generator.py")

        self._add(name="audio_synthesis", category=Category.MEDIA,
                  description="PCM tone/chord synthesis and TTS placeholder",
                  triggers=["tone", "sound", "audio", "music", "beep", "synth",
                            "sine", "chord", "hz", "frequency"],
                  event_topics_in=["audio.synthesize.request"],
                  event_topics_out=["audio.synthesize.result"],
                  actions=["generate_tone", "generate_chord", "text_to_speech_placeholder"],
                  file_path="components/audio_synthesis_engine.py")

        self._add(name="technical_visualization", category=Category.CREATION,
                  description="Engineering / math / geometry visual rendering",
                  triggers=["diagram", "geometry", "math visual", "technical diagram"],
                  actions=["render"],
                  file_path="gui/widgets/technical_visualization_engine.py")

        self._add(name="universal_data_viz", category=Category.CREATION,
                  description="Universal data → chart/dashboard renderer",
                  triggers=["chart", "graph", "plot", "dashboard", "visualize data"],
                  actions=["render"],
                  file_path="core/universal_data_visualizer.py")

        # ---- CREATION — chemistry / manufacturing sub-engines ----------
        self._add(name="chemistry_database", category=Category.SCIENCE,
                  description="Chemical compound lookup / search",
                  triggers=["chemistry", "compound", "molecule", "chemical"],
                  event_topics_in=["chemistry.database.query"],
                  event_topics_out=["chemistry.database.result"],
                  actions=["get_properties", "search_compounds"],
                  file_path="components/chemistry_database.py")

        self._add(name="schematic_engine", category=Category.SCIENCE,
                  description="Chemical reaction & process schematics",
                  triggers=["reaction", "process flow", "apparatus"],
                  event_topics_in=["chemistry.schematic.request"],
                  event_topics_out=["chemistry.schematic.result"],
                  actions=["render_reaction", "render_process_flow", "render_apparatus"],
                  file_path="components/schematic_engine.py")

        self._add(name="blueprint_engine", category=Category.ENGINEERING,
                  description="Manufacturing blueprint creation",
                  triggers=["blueprint", "technical drawing"],
                  event_topics_in=["manufacturing.blueprint.request"],
                  event_topics_out=["manufacturing.blueprint.result"],
                  actions=["create_blueprint"],
                  file_path="components/blueprint_engine.py")

        self._add(name="exploded_view", category=Category.ENGINEERING,
                  description="Exploded assembly views + bill of materials",
                  triggers=["exploded view", "assembly", "bom", "parts list"],
                  event_topics_in=["manufacturing.exploded_view.request"],
                  event_topics_out=["manufacturing.exploded_view.result"],
                  actions=["create_exploded_view", "add_part", "get_bill_of_materials"],
                  file_path="components/exploded_view_engine.py")

        self._add(name="metallurgy", category=Category.SCIENCE,
                  description="Alloy analysis + stress calculation",
                  triggers=["alloy", "metal", "stress", "metallurgy", "analyze alloy",
                            "steel", "iron", "copper", "aluminum"],
                  event_topics_in=["metallurgy.analyze.request"],
                  event_topics_out=["metallurgy.analyze.result"],
                  actions=["analyze_alloy", "calculate_stress"],
                  file_path="components/metallurgy_engine.py")

        self._add(name="biological_system", category=Category.SCIENCE,
                  description="Enzyme kinetics + DNA analysis",
                  triggers=["dna", "enzyme", "biology", "protein", "genetics"],
                  event_topics_in=["biology.model.request"],
                  event_topics_out=["biology.model.result"],
                  actions=["model_enzyme_kinetics", "analyze_dna_sequence"],
                  file_path="components/biological_system.py")

        self._add(name="alchemy_system", category=Category.SCIENCE,
                  description="Transmutation pathways + energy costs",
                  triggers=["alchemy", "transmute"],
                  event_topics_in=["alchemy.transmute.request"],
                  event_topics_out=["alchemy.transmute.result"],
                  actions=["transmute", "calculate_energy_cost"],
                  file_path="components/alchemy_system.py")

        self._add(name="manufacturing_engine", category=Category.ENGINEERING,
                  description="Process simulation, cost estimation, G-code",
                  triggers=["manufacturing", "cnc", "machining", "production"],
                  event_topics_in=["manufacturing.simulate.request"],
                  event_topics_out=["manufacturing.simulate.result"],
                  actions=["estimate_cost", "generate_gcode", "simulate_process"],
                  file_path="components/manufacturing_engine.py")

        self._add(name="visualization_dashboard", category=Category.SYSTEM,
                  description="Aggregated dashboard for chemistry/mfg sources",
                  triggers=["dashboard"],
                  event_topics_in=["dashboard.request"],
                  event_topics_out=["dashboard.update"],
                  actions=["register_data_source", "get_dashboard_data"],
                  file_path="components/visualization_dashboard.py")

        # ---- TRADING ---------------------------------------------------
        self._add(name="trading_component", category=Category.TRADING,
                  description="Live order placement, positions, risk gate, telemetry",
                  triggers=["place order", "buy", "sell", "cancel order", "position"],
                  event_topics_in=["trading.signal", "thoth.trading.decision",
                                   "trading.market_data_update"],
                  event_topics_out=["trading.order_update", "trading.profit",
                                    "trading.execution.quality"],
                  actions=["place_order", "cancel_order", "get_positions", "get_orders"],
                  file_path="components/trading/trading_component.py")

        self._add(name="trading_system", category=Category.TRADING,
                  description="Top-level trading orchestration + fallbacks",
                  triggers=["trading system", "execute", "run trading"],
                  event_topics_in=["trading.execute_order", "trading.analyze_market"],
                  event_topics_out=["trading.signal.generated", "trading.portfolio_update"],
                  actions=["execute_order", "analyze_market", "get_positions"],
                  file_path="core/trading_system.py")

        self._add(name="order_management", category=Category.TRADING,
                  description="Central async order lifecycle",
                  triggers=["order lifecycle", "order manager"],
                  event_topics_out=["order.created", "order.status.update"],
                  actions=["create_order", "cancel_order", "modify_order"],
                  file_path="core/order_management.py")

        self._add(name="real_exchange_executor", category=Category.TRADING,
                  description="CCXT-based real exchange execution",
                  triggers=["exchange", "execute order", "real trade"],
                  event_topics_out=["real_order.placed", "trading.order_filled"],
                  actions=["place_order", "cancel_order"],
                  file_path="core/real_exchange_executor.py")

        self._add(name="multichain_trade_executor", category=Category.TRADING,
                  description="Multichain DEX execution (EVM, Solana, ...)",
                  triggers=["dex", "swap", "multichain", "cross-chain"],
                  actions=["execute_swap"],
                  file_path="core/multichain_trade_executor.py")

        self._add(name="unified_portfolio_manager", category=Category.TRADING,
                  description="Cross-wallet/exchange portfolio aggregation",
                  triggers=["portfolio", "balance", "holdings"],
                  event_topics_out=["portfolio.unified.update"],
                  actions=["get_portfolio", "rebalance"],
                  file_path="core/unified_portfolio_manager.py")

        self._add(name="position_monitor", category=Category.TRADING,
                  description="Monitors open positions for TP/SL",
                  triggers=["take profit", "stop loss", "monitor positions"],
                  event_topics_out=["trading.position.exit", "trading.profit.update"],
                  actions=["monitor", "close_position"],
                  file_path="core/position_monitor.py")

        self._add(name="trading_analysis", category=Category.TRADING,
                  description="Technical indicators + performance analytics",
                  triggers=["indicator", "technical analysis", "ta"],
                  actions=["rsi", "macd", "bollinger", "atr", "sma", "ema"],
                  file_path="trading/trading_analysis.py")

        self._add(name="market_analyzer", category=Category.TRADING,
                  description="GUI-side technical indicator & signal helper",
                  triggers=["analyze market", "market signal"],
                  actions=["calculate_indicators", "generate_signal"],
                  file_path="gui/qt_frames/trading/market_analyzer.py")

        self._add(name="quantum_trading_optimizer", category=Category.TRADING,
                  description="Quantum-inspired portfolio & strategy optimization",
                  triggers=["quantum", "optimize portfolio", "vqe"],
                  event_topics_out=["trading.optimization.completed"],
                  actions=["optimize_portfolio", "optimize_strategy"],
                  file_path="core/quantum_trading_optimizer.py")

        self._add(name="ai_trading_system", category=Category.TRADING,
                  description="AI strategy lifecycle: create, backtest, optimize",
                  triggers=["ai strategy", "backtest", "optimize strategy"],
                  event_topics_in=["strategy.backtest"],
                  event_topics_out=["strategy.backtested", "strategy.optimized"],
                  actions=["create_strategy", "backtest", "optimize"],
                  file_path="core/ai_trading_system.py")

        self._add(name="trading_intelligence", category=Category.TRADING,
                  description="Competitive-edge analysis, anomalies, opportunities",
                  triggers=["intelligence", "opportunity", "edge", "anomaly"],
                  event_topics_out=["trading.analysis.response", "trading.signal",
                                    "trading.decision", "trading.performance.metrics"],
                  actions=["scan", "analyze"],
                  file_path="core/trading_intelligence.py")

        self._add(name="trading_hub", category=Category.TRADING,
                  description="DEX+CEX hub, arbitrage, meme scanner, whale tracker",
                  triggers=["arbitrage", "meme", "whale", "hub"],
                  event_topics_out=["gui.update.trading", "portfolio.updated"],
                  actions=["scan_arbitrage", "track_whales"],
                  file_path="trading/trading_hub.py")

        self._add(name="risk_manager", category=Category.TRADING,
                  description="Risk assessment, sizing, gate",
                  triggers=["risk", "sizing", "kelly"],
                  actions=["assess", "size_position"],
                  file_path="trading/risk_management.py")

        self._add(name="autonomous_orchestrator", category=Category.TRADING,
                  description="Autonomous module orchestration (hedging, sentiment, macro…)",
                  triggers=["autonomous", "auto trade", "automation"],
                  actions=["run_trading_cycle"],
                  file_path="components/autonomous_trading/autonomous_orchestrator.py")

        self._add(name="botsofwallstreet", category=Category.TRADING,
                  description="Autonomous idea posting agent",
                  triggers=["bots of wall street", "post idea"],
                  actions=["register", "post_idea"],
                  file_path="components/botsofwallstreet/agent.py")

        self._add(name="paper_autotrade_orchestrator", category=Category.TRADING,
                  description="Paper / auto-trade orchestration",
                  triggers=["paper trade", "simulate trade"],
                  event_topics_in=["ai.autotrade.analysis.ready"],
                  actions=["start", "stop"],
                  file_path="core/paper_autotrade_orchestrator.py")

        self._add(name="online_rl_trainer", category=Category.TRADING,
                  description="Online RL from closed paper trades",
                  triggers=["reinforcement learning", "rl", "learn from trades"],
                  event_topics_in=["autotrade.paper.trade_closed"],
                  actions=["update_model"],
                  file_path="core/online_rl_trainer.py")

        self._add(name="sentiment_analyzer", category=Category.TRADING,
                  description="Text sentiment scoring for markets/news",
                  triggers=["sentiment", "news analysis"],
                  actions=["analyze"],
                  file_path="kingdom_ai/analysis/sentiment_analyzer.py")

        self._add(name="thoth_live_integration", category=Category.TRADING,
                  description="Central live Thoth/Ollama ↔ trading loops",
                  triggers=["thoth trade", "live analysis"],
                  event_topics_in=["ai.analysis.start_24h"],
                  event_topics_out=["ai.autotrade.plan.generated", "ai.analysis.complete"],
                  actions=["start_24h_analysis"],
                  file_path="core/thoth_live_integration.py")

        # ---- BLOCKCHAIN ------------------------------------------------
        for chain in ["ethereum", "solana", "sui", "aptos", "cosmos", "polkadot",
                      "bsc", "avalanche", "arbitrum"]:
            self._add(name=f"blockchain_{chain}", category=Category.BLOCKCHAIN,
                      description=f"{chain.capitalize()} adapter (balance, tx, transfer)",
                      triggers=[chain, f"{chain} wallet", f"{chain} transfer"],
                      actions=["get_balance", "send_transaction", "get_transactions"],
                      file_path=f"blockchain/{chain}_adapter.py")

        self._add(name="wallet_manager", category=Category.BLOCKCHAIN,
                  description="Unified multi-chain wallet management",
                  triggers=["wallet", "balance", "send crypto"],
                  actions=["get_balance", "send", "list_accounts"],
                  file_path="core/wallet_manager.py")

        # ---- MINING ----------------------------------------------------
        self._add(name="mining_system", category=Category.MINING,
                  description="Stratum-based mining orchestration",
                  triggers=["mine", "mining", "hashrate", "miner"],
                  actions=["start_miner", "stop_miner", "get_hashrate"],
                  file_path="components/mining/mining_system.py")

        self._add(name="mining_intelligence", category=Category.MINING,
                  description="Airdrop & pool intelligence",
                  triggers=["airdrop", "pool", "mining intel"],
                  actions=["scan_opportunities"],
                  file_path="core/mining_intelligence.py")

        # ---- VOICE / AUDIO ---------------------------------------------
        self._add(name="voice_recognition", category=Category.VOICE,
                  description="Speech-to-text recognition",
                  triggers=["listen", "voice", "speak to me"],
                  actions=["recognize"],
                  file_path="core/voice/voice_recognition.py")

        self._add(name="text_to_speech", category=Category.VOICE,
                  description="Text-to-speech (Black Panther voice)",
                  triggers=["say", "speak", "tts", "text to speech"],
                  actions=["speak"],
                  file_path="core/voice/text_to_speech.py")

        # ---- VR --------------------------------------------------------
        self._add(name="vr_integration", category=Category.VR,
                  description="OpenXR VR integration + creation preview",
                  triggers=["vr", "virtual reality", "headset", "openxr"],
                  event_topics_in=["vr.creation.request", "creation.response"],
                  event_topics_out=["vr.tracking.update", "vr.creation.progress"],
                  actions=["start_session", "stop_session"],
                  file_path="core/vr_integration.py")

        # ---- HEALTH / BIOMETRIC ----------------------------------------
        self._add(name="wearable_biometric_streamer", category=Category.HEALTH,
                  description="Wearable device biometric streaming",
                  triggers=["wearable", "biometric", "heart rate", "hrv"],
                  event_topics_in=["biometric.stream.request"],
                  event_topics_out=["biometric.data.update"],
                  actions=["connect_device", "get_latest_metrics"],
                  file_path="components/wearable_biometric_streamer.py")

        self._add(name="eeg_signal_processor", category=Category.HEALTH,
                  description="EEG FFT + frequency-band extraction",
                  triggers=["eeg", "brainwave", "neural signal"],
                  event_topics_in=["eeg.process.request"],
                  event_topics_out=["eeg.process.result"],
                  actions=["process_signal", "extract_bands"],
                  file_path="components/eeg_signal_processor.py")

        self._add(name="lsl_sync_engine", category=Category.HEALTH,
                  description="LSL (Lab Streaming Layer) stream sync",
                  triggers=["lsl", "lab streaming", "sync stream"],
                  event_topics_in=["lsl.sync.request"],
                  event_topics_out=["lsl.sync.status"],
                  actions=["create_stream", "push_sample"],
                  file_path="components/lsl_sync_engine.py")

        self._add(name="neuroprotection", category=Category.HEALTH,
                  description="Cognitive-load / prompt-safety validation",
                  triggers=["neuroprotection", "cognitive load", "safe prompt"],
                  event_topics_in=["neuroprotection.check.request"],
                  event_topics_out=["neuroprotection.status.update"],
                  actions=["validate_input", "check_cognitive_load"],
                  file_path="components/neuroprotection_layer.py")

        self._add(name="hmd_integration", category=Category.HARDWARE,
                  description="Head-mounted display tracking",
                  triggers=["hmd", "headset tracking"],
                  event_topics_in=["hmd.command.request"],
                  event_topics_out=["hmd.tracking.update"],
                  actions=["connect_hmd", "get_tracking_data"],
                  file_path="components/hmd_integration.py")

        self._add(name="bone_conduction", category=Category.HARDWARE,
                  description="Bone-conduction audio driver",
                  triggers=["bone conduction", "bone audio"],
                  event_topics_in=["bone_conduction.command.request"],
                  event_topics_out=["bone_conduction.status.update"],
                  actions=["connect_device", "set_volume"],
                  file_path="components/bone_conduction_driver.py")

        self._add(name="hardware_interface", category=Category.HARDWARE,
                  description="Generic device registry + sensor read",
                  triggers=["device", "sensor", "hardware"],
                  event_topics_in=["hardware.command.request"],
                  event_topics_out=["hardware.status.update"],
                  actions=["register_device", "read_sensor", "list_devices"],
                  file_path="components/hardware_interface_layer.py")

        # ---- AI / BRAIN / ROUTER / MEMORY ------------------------------
        self._add(name="brain_router", category=Category.AI,
                  description="Primary brain router (visual/trading/sentience routing)",
                  triggers=["brain", "route"],
                  event_topics_in=["brain.request", "visual.request"],
                  event_topics_out=["brain.visual.request", "brain.route_decision"],
                  actions=["route"],
                  file_path="kingdom_ai/ai/brain_router.py")

        self._add(name="unified_brain_router", category=Category.AI,
                  description="Dual-backend brain router (Ollama + NemoClaw)",
                  triggers=["unified brain", "nemoclaw", "secure brain"],
                  event_topics_in=["brain.request"],
                  event_topics_out=["brain.status_update", "nemoclaw.response",
                                    "thoth.request"],
                  actions=["route", "get_routing_stats"],
                  file_path="core/unified_brain_router.py")

        self._add(name="thoth_ollama_connector", category=Category.AI,
                  description="Direct Ollama connector for Thoth chat/voice",
                  triggers=["thoth", "ollama", "chat", "ask"],
                  event_topics_in=["thoth.request", "ollama.request",
                                   "ai.message.send"],
                  event_topics_out=["thoth.response", "thoth.streaming_response"],
                  actions=["generate", "chat"],
                  file_path="core/thoth_ollama_connector.py")

        self._add(name="nemoclaw_bridge", category=Category.AI,
                  description="NVIDIA NemoClaw secure sandbox bridge",
                  triggers=["sandbox", "secure execution", "nemoclaw"],
                  actions=["send_to_nemoclaw"],
                  file_path="core/nemoclaw_bridge.py")

        self._add(name="security_policy_manager", category=Category.SECURITY,
                  description="Security policy + prompt classification",
                  triggers=["security policy", "classify prompt"],
                  actions=["analyze_prompt_security", "get_security_level"],
                  file_path="core/security_policy_manager.py")

        self._add(name="creation_orchestrator", category=Category.CREATION,
                  description="Multi-engine creation pipeline planner + executor",
                  triggers=["orchestrate creation", "multi engine", "pipeline"],
                  actions=["parse_request", "execute_pipeline"],
                  file_path="core/creation_orchestrator.py")

        # ---- MEMPALACE --------------------------------------------------
        self._add(name="memory_palace_manager", category=Category.MEMORY,
                  description="Structured memory palace",
                  triggers=["remember", "memory", "recall"],
                  actions=["store", "recall"],
                  file_path="components/memory_palace_manager.py")

        self._add(name="memory_persistence_layer", category=Category.MEMORY,
                  description="Persistent KV store for memories",
                  triggers=["persist memory", "save memory"],
                  actions=["save", "load"],
                  file_path="components/memory_persistence_layer.py")

        self._add(name="mempalace_bridge", category=Category.MEMORY,
                  description="Bridge between MemPalace and event bus",
                  triggers=["memory bridge"],
                  actions=["write_memory", "read_memory"],
                  file_path="components/mempalace_bridge.py")

        self._add(name="ollama_memory_integration", category=Category.MEMORY,
                  description="Ollama-powered embeddings + semantic search",
                  triggers=["semantic memory", "embedding", "vector search"],
                  event_topics_in=["memory.enhance.request"],
                  event_topics_out=["memory.enhance.result"],
                  actions=["generate_embedding", "semantic_search"],
                  file_path="components/ollama_memory_integration.py")

        self._add(name="mempalace_mcp_server", category=Category.MEMORY,
                  description="MCP server exposing memory tools",
                  triggers=["mcp memory", "memory tools"],
                  actions=["list_tools", "handle_tool_call"],
                  file_path="components/mempalace_mcp_server.py")

        # ---- ORCHESTRATORS / SUBSYSTEMS ---------------------------------
        self._add(name="harmonic_orchestrator_v3", category=Category.AI,
                  description="Harmonic multi-subsystem orchestrator",
                  triggers=["harmonic", "orchestrator v3"],
                  event_topics_in=["orchestrator.task.request"],
                  event_topics_out=["orchestrator.task.result"],
                  actions=["orchestrate", "register_subsystem", "get_harmony_score"],
                  file_path="components/harmonic_orchestrator_v3.py")

        self._add(name="language_learning_hub", category=Category.AI,
                  description="Language learning + vocabulary",
                  triggers=["language", "translate", "vocabulary", "spanish",
                            "french", "chinese"],
                  event_topics_in=["language.learn.request"],
                  event_topics_out=["language.learn.result"],
                  actions=["get_vocabulary", "translate"],
                  file_path="components/language_learning_hub.py")


# ──────────────────────────────────────────────────────────────────────
# Global singleton accessor
# ──────────────────────────────────────────────────────────────────────

_GLOBAL_REGISTRY: Optional[KingdomSystemRegistry] = None
_GLOBAL_LOCK = threading.RLock()


def get_registry(event_bus: Any = None) -> KingdomSystemRegistry:
    global _GLOBAL_REGISTRY
    with _GLOBAL_LOCK:
        if _GLOBAL_REGISTRY is None:
            _GLOBAL_REGISTRY = KingdomSystemRegistry(event_bus=event_bus)
        elif event_bus is not None and _GLOBAL_REGISTRY.event_bus is None:
            _GLOBAL_REGISTRY.event_bus = event_bus
        return _GLOBAL_REGISTRY


def reset_registry() -> None:
    """Test-only: clear the global registry."""
    global _GLOBAL_REGISTRY
    with _GLOBAL_LOCK:
        _GLOBAL_REGISTRY = None
