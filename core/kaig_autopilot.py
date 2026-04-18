"""
Kingdom AI — $KAIG AutoPilot (SOTA 2026)
Fully autonomous rollout manager for $KAIG (KAI Gold).

Research-backed design (2026):
  - ElizaOS/ai16z: Autonomous agent treasury management + on-chain operations
  - Hyperliquid: Automated revenue → buyback with zero human intervention
  - Grass/Helium DePIN: Self-managing node reward distribution
  - web3-ethereum-defi: Programmatic Uniswap V3 pool creation + liquidity
  - CertiK/Sherlock: Automated audit pipeline integration

Creator Mode:  Full rollout control, AI executes + alerts when human needed
Consumer Mode: Read-only updates, auto wallet creation, node participation only

The autopilot handles:
  Phase 0 (Genesis):       100% automated — buybacks, escrow, node rewards, wallet creation
  Phase 1 (Accumulation):  95% automated — alerts creator at treasury milestones
  Phase 2 (Stabilization): 90% automated — alerts for governance setup, staking launch
  Phase 3 (Pre-Listing):   70% automated — alerts for audit approval, DEX setup, market makers
  Phase 4 (Listing):       60% automated — alerts for CEX applications, DAO launch
"""

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("KingdomAI.KAIG.AutoPilot")

_orch = None
_ORCH_AVAILABLE = False

def _ensure_orch():
    global _orch, _ORCH_AVAILABLE
    if _ORCH_AVAILABLE:
        return True
    try:
        from core.ollama_gateway import orchestrator as _o, get_ollama_url as _gou
        _orch = _o
        globals()["get_ollama_url"] = _gou
        _ORCH_AVAILABLE = True
        return True
    except Exception:
        return False

def get_ollama_url():
    return "http://localhost:11434"

_ensure_orch()

# Paths
CONFIG_DIR = os.path.join("config", "kaig")
AUTOPILOT_STATE_PATH = os.path.join(CONFIG_DIR, "autopilot_state.json")
ALERTS_PATH = os.path.join(CONFIG_DIR, "creator_alerts.json")
WALLET_PATH = os.path.join(CONFIG_DIR, "wallets.json")

# Timing
AUTOPILOT_TICK_SECONDS = 60          # Check every 60 seconds
ESCROW_CHECK_HOURS = 24              # Check escrow releases daily
BUYBACK_CHECK_SECONDS = 300          # Check buyback eligibility every 5 min
NODE_REWARD_CHECK_SECONDS = 3600     # Distribute node rewards hourly
PHASE_CHECK_SECONDS = 3600           # Re-evaluate phase hourly
WALLET_BACKUP_HOURS = 24             # Backup wallet state daily


class CreatorAlert:
    """An alert that requires creator attention."""

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_CRITICAL = "critical"

    def __init__(self, title: str, message: str, action_needed: str,
                 priority: str = "medium", category: str = "general",
                 auto_resolve: bool = False):
        self.id = f"alert_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self.title = title
        self.message = message
        self.action_needed = action_needed
        self.priority = priority
        self.category = category
        self.auto_resolve = auto_resolve
        self.created_at = datetime.utcnow().isoformat()
        self.resolved = False
        self.resolved_at = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "title": self.title, "message": self.message,
            "action_needed": self.action_needed, "priority": self.priority,
            "category": self.category, "auto_resolve": self.auto_resolve,
            "created_at": self.created_at, "resolved": self.resolved,
            "resolved_at": self.resolved_at,
        }


class KAIGWalletManager:
    """Auto-creates and manages KAIG wallets for creator and consumer versions."""

    def __init__(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.wallets = self._load()

    def _load(self) -> Dict:
        if os.path.exists(WALLET_PATH):
            try:
                with open(WALLET_PATH, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"wallets": {}, "created_at": datetime.utcnow().isoformat()}

    def _save(self):
        with open(WALLET_PATH, "w") as f:
            json.dump(self.wallets, f, indent=2)

    def ensure_wallet(self, wallet_id: str, wallet_type: str = "user",
                      label: str = "") -> Dict:
        """Ensure a KAIG wallet exists. Auto-creates if not found.

        Args:
            wallet_id: Unique identifier (e.g., 'creator', 'consumer_<device_id>')
            wallet_type: 'creator', 'consumer', 'treasury', 'escrow', 'community'
            label: Human-readable label

        Returns:
            Wallet info dict with address, type, balance reference
        """
        if wallet_id in self.wallets.get("wallets", {}):
            return self.wallets["wallets"][wallet_id]

        # Generate a deterministic but unique KAIG address
        import hashlib
        seed = f"kaig_{wallet_id}_{self.wallets.get('created_at', '')}".encode()
        addr_hash = hashlib.sha256(seed).hexdigest()
        kaig_address = f"KAIG_{addr_hash[:40]}"

        wallet = {
            "wallet_id": wallet_id,
            "kaig_address": kaig_address,
            "wallet_type": wallet_type,
            "label": label or wallet_id,
            "created_at": datetime.utcnow().isoformat(),
            "auto_created": True,
        }

        self.wallets.setdefault("wallets", {})[wallet_id] = wallet
        self._save()
        logger.info("Auto-created KAIG wallet: %s → %s (%s)",
                     wallet_id, kaig_address[:20] + "...", wallet_type)
        return wallet

    def get_wallet(self, wallet_id: str) -> Optional[Dict]:
        return self.wallets.get("wallets", {}).get(wallet_id)

    def list_wallets(self) -> Dict[str, Dict]:
        return self.wallets.get("wallets", {})


class KAIGAutoPilot:
    """
    Autonomous $KAIG rollout manager.
    Handles all phases with minimal human intervention.
    Creator version: full control + alerts.
    Consumer version: read-only + auto wallet + node participation.
    """

    _instance = None

    @classmethod
    def get_instance(cls, event_bus=None, is_creator: bool = True):
        if cls._instance is None:
            cls._instance = cls(event_bus=event_bus, is_creator=is_creator)
        return cls._instance

    def __init__(self, event_bus=None, is_creator: bool = True):
        self.event_bus = event_bus
        self.is_creator = is_creator
        self.wallet_manager = KAIGWalletManager()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._alerts: List[Dict] = self._load_alerts()
        self._state = self._load_state()
        self._last_buyback_check = 0.0
        self._last_escrow_check = 0.0
        self._last_node_reward_check = 0.0
        self._last_phase_check = 0.0
        self._engine = None

        # Auto-create system wallets on init
        self._ensure_system_wallets()

        # Subscribe to events
        if self.event_bus:
            self.event_bus.subscribe("kaig.autopilot.start", self._on_start)
            self.event_bus.subscribe("kaig.autopilot.stop", self._on_stop)
            self.event_bus.subscribe("kaig.alert.resolve", self._on_alert_resolve)
            if self.is_creator:
                self.event_bus.subscribe("kaig.autopilot.override", self._on_override)

        logger.info("KAIG AutoPilot initialized (mode=%s)",
                     "CREATOR" if is_creator else "CONSUMER")

    def _get_engine(self):
        if self._engine:
            return self._engine
        try:
            from core.kaig_engine import KAIGEngine
            self._engine = KAIGEngine.get_instance()
            return self._engine
        except Exception:
            return None

    def _ensure_system_wallets(self):
        """Auto-create all required system wallets."""
        self.wallet_manager.ensure_wallet("treasury", "treasury", "AI Treasury")
        self.wallet_manager.ensure_wallet("escrow", "escrow", "Escrow Vault")
        self.wallet_manager.ensure_wallet("community", "community", "Community Pool")
        self.wallet_manager.ensure_wallet("team", "team", "Team/Dev Vesting")
        self.wallet_manager.ensure_wallet("burn", "burn", "Burn Address (dead)")

        if self.is_creator:
            self.wallet_manager.ensure_wallet("creator", "creator", "Creator Wallet")
        else:
            # Consumer gets a unique wallet based on machine ID
            device_id = self._get_device_id()
            self.wallet_manager.ensure_wallet(
                f"consumer_{device_id}", "consumer",
                f"Consumer Wallet ({device_id[:8]})")

    def _get_device_id(self) -> str:
        """Get a unique device identifier for consumer wallets."""
        import hashlib
        try:
            import platform
            raw = f"{platform.node()}_{platform.machine()}_{os.getlogin()}"
            return hashlib.sha256(raw.encode()).hexdigest()[:16]
        except Exception:
            return hashlib.sha256(os.urandom(16)).hexdigest()[:16]

    # ── ALERT SYSTEM ─────────────────────────────────────────────

    def _load_alerts(self) -> List[Dict]:
        if os.path.exists(ALERTS_PATH):
            try:
                with open(ALERTS_PATH, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_alerts(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(ALERTS_PATH, "w") as f:
            json.dump(self._alerts, f, indent=2)

    def create_alert(self, title: str, message: str, action_needed: str,
                     priority: str = "medium", category: str = "general"):
        """Create a creator alert. Only meaningful in creator mode."""
        alert = CreatorAlert(title, message, action_needed, priority, category)
        alert_dict = alert.to_dict()
        self._alerts.append(alert_dict)
        self._save_alerts()

        if self.event_bus:
            self.event_bus.publish("kaig.creator.alert", alert_dict)

        logger.info("CREATOR ALERT [%s]: %s — %s", priority.upper(), title, action_needed)
        return alert_dict

    def get_pending_alerts(self) -> List[Dict]:
        return [a for a in self._alerts if not a.get("resolved")]

    def resolve_alert(self, alert_id: str):
        for a in self._alerts:
            if a["id"] == alert_id:
                a["resolved"] = True
                a["resolved_at"] = datetime.utcnow().isoformat()
                self._save_alerts()
                if self.event_bus:
                    self.event_bus.publish("kaig.alert.resolved", a)
                return True
        return False

    def _on_alert_resolve(self, data):
        if isinstance(data, dict):
            self.resolve_alert(data.get("alert_id", ""))

    def _on_override(self, data):
        """Creator can override autopilot decisions."""
        if isinstance(data, dict) and self.is_creator:
            action = data.get("action", "")
            logger.info("Creator override: %s", action)

    # ── STATE PERSISTENCE ────────────────────────────────────────

    def _load_state(self) -> Dict:
        if os.path.exists(AUTOPILOT_STATE_PATH):
            try:
                with open(AUTOPILOT_STATE_PATH, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "current_phase": "phase_0_genesis",
            "started_at": datetime.utcnow().isoformat(),
            "total_auto_buybacks": 0,
            "total_auto_escrow_releases": 0,
            "total_node_rewards_distributed": 0.0,
            "total_alerts_created": 0,
            "last_tick": None,
        }

    def _save_state(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self._state["last_tick"] = datetime.utcnow().isoformat()
        with open(AUTOPILOT_STATE_PATH, "w") as f:
            json.dump(self._state, f, indent=2)

    # ── MAIN AUTOPILOT LOOP ──────────────────────────────────────

    def start(self):
        """Start the autonomous rollout manager."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._autopilot_loop, daemon=True)
        self._thread.start()
        logger.info("KAIG AutoPilot STARTED (mode=%s)",
                     "CREATOR" if self.is_creator else "CONSUMER")
        if self.event_bus:
            self.event_bus.publish("kaig.autopilot.status", {
                "status": "running", "mode": "creator" if self.is_creator else "consumer"
            })

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self._save_state()
        logger.info("KAIG AutoPilot STOPPED")

    def _on_start(self, data=None):
        self.start()

    def _on_stop(self, data=None):
        self.stop()

    def _autopilot_loop(self):
        """Main autonomous loop — runs every AUTOPILOT_TICK_SECONDS."""
        logger.info("AutoPilot loop running...")
        while self._running:
            try:
                now = time.time()

                # Phase detection (hourly)
                if now - self._last_phase_check >= PHASE_CHECK_SECONDS:
                    self._check_phase_transition()
                    self._last_phase_check = now

                # Only creator handles active management
                if self.is_creator:
                    # Buyback check (every 5 min)
                    if now - self._last_buyback_check >= BUYBACK_CHECK_SECONDS:
                        self._auto_buyback()
                        self._last_buyback_check = now

                    # Escrow release check (daily)
                    if now - self._last_escrow_check >= ESCROW_CHECK_HOURS * 3600:
                        self._auto_escrow_release()
                        self._last_escrow_check = now

                    # Node rewards (hourly)
                    if now - self._last_node_reward_check >= NODE_REWARD_CHECK_SECONDS:
                        self._auto_node_rewards()
                        self._last_node_reward_check = now

                    # Phase-specific autonomous actions
                    self._run_phase_actions()

                self._save_state()

            except Exception as e:
                logger.error("AutoPilot tick error: %s", e)

            time.sleep(AUTOPILOT_TICK_SECONDS)

    # ── AUTONOMOUS ACTIONS ───────────────────────────────────────

    def _auto_buyback(self):
        """AI-managed automatic buyback execution.

        The treasury's _execute_buyback now consults the Ollama brain for
        optimal timing and impact assessment. The autopilot triggers it,
        and the AI decides whether to proceed, defer, or adjust.
        """
        engine = self._get_engine()
        if not engine:
            return
        try:
            treasury = engine.treasury
            pending = treasury.treasury.get("pending_buyback_usd", 0.0)
            if pending >= 10.0:
                result = treasury._execute_buyback(pending, "autopilot")
                status = result.get("status", "")
                if status == "buyback_executed":
                    self._state["total_auto_buybacks"] = \
                        self._state.get("total_auto_buybacks", 0) + 1
                    logger.info("AUTO-BUYBACK: $%.2f → %.2f KAIG (AI factor: %.2f)",
                                 pending, result.get("kaig_acquired", 0),
                                 result.get("ai_impact_factor", 1.0))
                elif status == "ai_deferred":
                    logger.info("AUTO-BUYBACK DEFERRED by AI: %s",
                                 result.get("reasoning", ""))
        except Exception as e:
            logger.debug("Auto-buyback check: %s", e)

    def _auto_escrow_release(self):
        """Automatic escrow release processing."""
        engine = self._get_engine()
        if not engine:
            return
        try:
            result = engine.check_escrow_releases()
            if result and result.get("released"):
                self._state["total_auto_escrow_releases"] = \
                    self._state.get("total_auto_escrow_releases", 0) + 1
                logger.info("AUTO-ESCROW: Released %s KAIG (re-locked %.0f%%)",
                             result.get("amount", 0), result.get("relock_pct", 75))
        except Exception as e:
            logger.debug("Auto-escrow check: %s", e)

    def _auto_node_rewards(self):
        """Distribute rewards to running KAIG nodes."""
        engine = self._get_engine()
        if not engine:
            return
        try:
            if hasattr(engine, 'node') and engine.node.is_running:
                reward = engine.node.heartbeat()
                if reward and reward.get("reward_earned", 0) > 0:
                    earned = reward["reward_earned"]
                    self._state["total_node_rewards_distributed"] = \
                        self._state.get("total_node_rewards_distributed", 0) + earned
                    logger.debug("AUTO-NODE-REWARD: %.4f KAIG distributed", earned)
        except Exception as e:
            logger.debug("Auto-node-reward: %s", e)

    def _ai_phase_analysis(self, phase_id: str, reserves: float,
                           buybacks: int, price: float) -> str:
        """Consult the Ollama brain for phase-specific strategic recommendations."""
        if not _ensure_orch():
            return ""
        try:
            import requests
            model = _orch.get_model_for_task("kaig")
            url = get_ollama_url()
            prompt = (
                f"You are the KAIG AutoPilot AI. Current phase: {phase_id}\n"
                f"Treasury reserves: ${reserves:,.2f}\n"
                f"Total buybacks: {buybacks}\n"
                f"KAIG price: ${price:.4f}\n"
                f"Target: $10.00\n\n"
                f"Give ONE actionable recommendation for this phase in 1-2 sentences. "
                f"Focus on what should happen NEXT to advance KAIG toward launch."
            )
            resp = requests.post(
                f"{url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": 100, "temperature": 0.4},
                      "keep_alive": -1},
                timeout=30,
            )
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                if text:
                    logger.info("KAIG AI phase recommendation: %s", text[:200])
                    return text[:200]
        except Exception as e:
            logger.debug("AI phase analysis unavailable: %s", e)
        return ""

    def _check_phase_transition(self):
        """Auto-detect phase transitions with AI analysis and alert creator."""
        engine = self._get_engine()
        if not engine:
            return
        try:
            phase = engine.get_current_phase()
            new_phase = phase.get("current_phase_id", "phase_0_genesis")
            old_phase = self._state.get("current_phase", "phase_0_genesis")

            if new_phase != old_phase:
                self._state["current_phase"] = new_phase
                logger.info("PHASE TRANSITION: %s → %s", old_phase, new_phase)

                # Get AI recommendation for the new phase
                status = engine.get_full_status()
                reserves = status.get("treasury", {}).get("total_reserves_usd", 0)
                buybacks = status.get("treasury", {}).get("num_buybacks", 0)
                price = status.get("current_price", 0.10)
                ai_rec = self._ai_phase_analysis(new_phase, reserves, buybacks, price)

                if self.is_creator:
                    msg = (
                        f"KAIG ecosystem has transitioned from {old_phase} to {new_phase}. "
                        f"New objectives and AI actions are now active."
                    )
                    if ai_rec:
                        msg += f"\n\nAI Recommendation: {ai_rec}"
                    self.create_alert(
                        f"Phase Transition: {phase.get('phase_name', new_phase)}",
                        msg,
                        "Review new phase objectives in the Roadmap tab.",
                        priority="high", category="phase_transition"
                    )
                if self.event_bus:
                    self.event_bus.publish("kaig.phase.transition", {
                        "old_phase": old_phase, "new_phase": new_phase,
                        "phase_name": phase.get("phase_name", ""),
                        "ai_recommendation": ai_rec,
                    })
        except Exception as e:
            logger.debug("Phase check: %s", e)

    def _run_phase_actions(self):
        """Execute phase-specific autonomous actions with AI guidance."""
        phase = self._state.get("current_phase", "phase_0_genesis")
        engine = self._get_engine()
        if not engine:
            return

        try:
            status = engine.get_full_status()
            treasury = status.get("treasury", {})
            reserves = treasury.get("total_reserves_usd", 0)
            num_buybacks = treasury.get("num_buybacks", 0)
            price = status.get("current_price", 0.10)

            if phase == "phase_0_genesis":
                self._phase_0_actions(reserves, num_buybacks, price)
            elif phase == "phase_1_accumulation":
                self._phase_1_actions(reserves, num_buybacks, price)
            elif phase == "phase_2_stabilization":
                self._phase_2_actions(reserves, num_buybacks, price)
            elif phase == "phase_3_pre_listing":
                self._phase_3_actions(reserves, num_buybacks, price)
            elif phase == "phase_4_listing":
                self._phase_4_actions(reserves, num_buybacks, price)

            # Periodic AI phase check (every 60 ticks = ~1hr)
            tick_count = self._state.get("_phase_ai_tick", 0) + 1
            self._state["_phase_ai_tick"] = tick_count
            if tick_count % 60 == 0:
                ai_rec = self._ai_phase_analysis(phase, reserves, num_buybacks, price)
                if ai_rec and self.event_bus:
                    self.event_bus.publish("kaig.autopilot.ai_insight", {
                        "phase": phase,
                        "recommendation": ai_rec,
                        "reserves": reserves,
                        "price": price,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
        except Exception as e:
            logger.debug("Phase action error: %s", e)

    # ── PHASE-SPECIFIC ACTIONS ───────────────────────────────────
    # Each phase has:  AI auto-actions  +  creator alerts when human needed

    def _phase_0_actions(self, reserves, buybacks, price):
        """Phase 0: Genesis — mostly automated, minimal alerts."""
        # Alert at first successful buyback
        if buybacks == 1 and not self._alert_exists("first_buyback"):
            self.create_alert(
                "First Buyback Executed!",
                f"The AI treasury executed its first KAIG buyback. "
                f"Treasury reserves: ${reserves:,.2f}. "
                f"The revenue → buyback pipeline is operational.",
                "No action needed — this is an informational milestone.",
                priority="low", category="milestone"
            )

        # Alert when approaching Phase 1 threshold
        if reserves >= 40000 and not self._alert_exists("approaching_phase1"):
            self.create_alert(
                "Approaching Phase 1 (Accumulation)",
                f"Treasury reserves at ${reserves:,.2f} — approaching $50K threshold. "
                f"Phase 1 will activate enhanced buyback optimization.",
                "No action needed — phase will transition automatically.",
                priority="low", category="milestone"
            )

    def _phase_1_actions(self, reserves, buybacks, price):
        """Phase 1: Accumulation — alert at treasury milestones."""
        if reserves >= 100000 and not self._alert_exists("treasury_100k"):
            self.create_alert(
                "Treasury Hit $100K!",
                f"KAIG treasury reserves reached ${reserves:,.2f}. "
                f"This is a major milestone for the AI-managed treasury.",
                "Consider beginning staking infrastructure preparation.",
                priority="medium", category="milestone"
            )

    def _phase_2_actions(self, reserves, buybacks, price):
        """Phase 2: Stabilization — alerts for governance + staking."""
        if not self._alert_exists("governance_setup"):
            self.create_alert(
                "Governance Setup Required",
                "Phase 2 requires implementing KAIG governance voting. "
                "This allows the community to vote on proposals.",
                "Review governance smart contract templates and deploy. "
                "AI will handle vote counting and proposal execution.",
                priority="high", category="human_action"
            )
        if not self._alert_exists("staking_launch"):
            self.create_alert(
                "Staking Program Launch",
                "Phase 2 includes launching the 12% APY staking program. "
                "Staking contract needs deployment and testing.",
                "Deploy staking smart contract. AI will manage reward distribution.",
                priority="high", category="human_action"
            )
        if not self._alert_exists("audit_prep"):
            self.create_alert(
                "Smart Contract Audit Preparation",
                "Begin preparing for smart contract audit. "
                "Auditors (CertiK, Sherlock, Trail of Bits) need 2-4 weeks lead time.",
                "Select audit firm and submit codebase for review. "
                "AI can compile the audit package automatically.",
                priority="medium", category="human_action"
            )

    def _phase_3_actions(self, reserves, buybacks, price):
        """Phase 3: Pre-Listing — more human involvement needed."""
        if not self._alert_exists("audit_submit"):
            self.create_alert(
                "Submit Smart Contract for Audit",
                f"Treasury at ${reserves:,.2f}. Ready for mainnet deployment. "
                "Smart contract audit is a prerequisite for exchange listing.",
                "Submit to CertiK/Sherlock. AI will track audit progress. "
                "Estimated cost: $5K-50K depending on complexity.",
                priority="critical", category="human_action"
            )
        if not self._alert_exists("dex_liquidity"):
            self.create_alert(
                "DEX Liquidity Pool Setup",
                "Prepare Uniswap V3 / Raydium liquidity pool. "
                "AI can execute the pool creation via web3.py / eth-defi library. "
                "Requires deployer wallet with ETH for gas + KAIG + USDC for liquidity.",
                "Fund deployer wallet with ETH + USDC. AI will: "
                "1) Deploy ERC-20 contract, 2) Create Uniswap V3 pool, "
                "3) Add initial liquidity, 4) Verify on Etherscan. "
                "All programmatic via web3.py — minimal human intervention.",
                priority="critical", category="human_action"
            )
        if not self._alert_exists("market_makers"):
            self.create_alert(
                "Market Maker Relationships",
                "Contact market makers for launch liquidity. "
                "AI can draft outreach emails and track responses.",
                "Approve AI-drafted outreach to market makers: "
                "Wintermute, GSR, Alameda-successors, DWF Labs.",
                priority="high", category="human_action"
            )

    def _phase_4_actions(self, reserves, buybacks, price):
        """Phase 4: Listing — AI handles market making, alerts for CEX apps."""
        if not self._alert_exists("cex_applications"):
            self.create_alert(
                "Centralized Exchange Applications",
                "Apply to Tier-2 exchanges: KuCoin, Gate.io, MEXC. "
                "AI can fill out application forms with project data. "
                "Most exchanges require: audit report, whitepaper, team info, treasury proof.",
                "Review and submit AI-prepared exchange applications. "
                "Listing fees vary: $10K-100K for Tier-2, $500K+ for Tier-1.",
                priority="critical", category="human_action"
            )
        if not self._alert_exists("dao_launch"):
            self.create_alert(
                "KAIG DAO Governance Launch",
                "Deploy KAIG DAO for community governance. "
                "AI can deploy Governor + Timelock contracts via web3.py.",
                "Approve DAO constitution and deploy. AI handles the rest.",
                priority="high", category="human_action"
            )

    def _alert_exists(self, keyword: str) -> bool:
        """Check if an alert with this keyword already exists."""
        for a in self._alerts:
            if keyword.lower() in a.get("title", "").lower() or \
               keyword.lower() in a.get("category", "").lower():
                return True
        return False

    # ── PUBLIC API ───────────────────────────────────────────────

    def get_status(self) -> Dict:
        """Get autopilot status for UI display."""
        engine = self._get_engine()
        phase_info = {}
        if engine:
            try:
                phase_info = engine.get_current_phase()
            except Exception:
                pass

        return {
            "running": self._running,
            "mode": "creator" if self.is_creator else "consumer",
            "current_phase": self._state.get("current_phase", "phase_0_genesis"),
            "phase_info": phase_info,
            "total_auto_buybacks": self._state.get("total_auto_buybacks", 0),
            "total_escrow_releases": self._state.get("total_auto_escrow_releases", 0),
            "total_node_rewards": self._state.get("total_node_rewards_distributed", 0),
            "pending_alerts": len(self.get_pending_alerts()),
            "total_alerts": len(self._alerts),
            "wallets": len(self.wallet_manager.list_wallets()),
            "last_tick": self._state.get("last_tick"),
        }

    def get_automation_matrix(self) -> Dict[str, Dict]:
        """Return what AI handles vs what needs human action per phase."""
        return {
            "phase_0_genesis": {
                "automation_pct": 100,
                "ai_handles": [
                    "Buyback execution (50% of trading profits)",
                    "Escrow release processing (monthly, 75% re-lock)",
                    "Node reward distribution (0.5 KAIG/hr)",
                    "Wallet auto-creation (creator + consumer)",
                    "Price tracking and supply management",
                    "Transaction burn processing (0.1%)",
                    "Referral KAIG bonus crediting",
                    "Treasury reserve allocation (BTC/ETH/USDC)",
                ],
                "human_needed": [],
            },
            "phase_1_accumulation": {
                "automation_pct": 95,
                "ai_handles": [
                    "Optimized buyback timing (price-impact aware)",
                    "Dynamic node reward rate adjustment",
                    "Burn rate vs supply release monitoring",
                    "Weekly KAIG economy report generation",
                    "Treasury diversification across assets",
                ],
                "human_needed": [
                    "Review milestone alerts (informational only)",
                ],
            },
            "phase_2_stabilization": {
                "automation_pct": 90,
                "ai_handles": [
                    "Price stability analysis and defense",
                    "Liquidity depth simulation",
                    "Treasury allocation optimization",
                    "Staking reward distribution (after launch)",
                    "Governance vote counting (after setup)",
                ],
                "human_needed": [
                    "Deploy governance smart contract",
                    "Launch staking program",
                    "Select and engage audit firm",
                ],
            },
            "phase_3_pre_listing": {
                "automation_pct": 70,
                "ai_handles": [
                    "ERC-20 contract deployment (web3.py)",
                    "Uniswap V3 pool creation (eth-defi library)",
                    "Initial liquidity addition (programmatic)",
                    "Etherscan verification (automated)",
                    "Anti-bot protection configuration",
                    "Launch price modeling and scenarios",
                    "Market maker outreach drafting",
                    "Exchange application form filling",
                ],
                "human_needed": [
                    "Approve audit submission + pay audit fee",
                    "Fund deployer wallet (ETH + USDC)",
                    "Approve DEX pool creation parameters",
                    "Sign market maker agreements",
                ],
            },
            "phase_4_listing": {
                "automation_pct": 60,
                "ai_handles": [
                    "Real-time market making optimization",
                    "Cross-exchange arbitrage monitoring",
                    "Dynamic buyback execution",
                    "DAO proposal analysis and execution",
                    "Regulatory compliance monitoring",
                    "Community analytics and reporting",
                ],
                "human_needed": [
                    "Submit and review CEX applications",
                    "Pay exchange listing fees",
                    "Approve DAO constitution",
                    "Review legal/regulatory matters",
                ],
            },
        }

    def get_wallet_for_version(self, is_creator: bool,
                                device_id: str = "") -> Dict:
        """Get or create the appropriate KAIG wallet."""
        if is_creator:
            return self.wallet_manager.ensure_wallet(
                "creator", "creator", "Creator Master Wallet")
        else:
            did = device_id or self._get_device_id()
            return self.wallet_manager.ensure_wallet(
                f"consumer_{did}", "consumer",
                f"Consumer Wallet ({did[:8]})")
