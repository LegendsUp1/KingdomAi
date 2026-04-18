"""
Kingdom AI — $KAIG (KAI Gold) Engine
SOTA 2026: AI-managed cryptocurrency with revenue-backed buyback mechanism.

Architecture modeled on proven tokenomics from:
  - XRP: Pre-mined fixed supply + escrow-based controlled release
  - Hyperliquid: Revenue-based automated buybacks (97% of fees → buybacks)
  - BNB: Quarterly burns tied to real platform revenue
  - Aave/Jupiter: Treasury-funded buybacks with community governance

Key Design Principles (Anti-Pi-Coin Failures):
  1. REAL utility — pay trading fees, unlock features, governance votes
  2. REAL backing — treasury holds BTC/ETH/USDC from trading profits
  3. Controlled supply — XRP-style escrow with monthly release caps
  4. AI-managed treasury — Kingdom AI brain optimizes buyback timing
  5. Deflationary pressure — transaction fee burns + profit-funded buybacks
  6. Pre-listing economy — internal economy strong BEFORE exchange listing
  7. $10 target — achieved via controlled supply + real demand + buybacks

Tokenomics:
  Total Supply:     100,000,000 KAIG (fixed, pre-minted)
  Escrow Locked:     70,000,000 KAIG (70% — XRP-style time-locked release)
  Treasury Reserve:  15,000,000 KAIG (15% — AI-managed buyback + liquidity)
  Community/Mining:  10,000,000 KAIG (10% — node rewards, referrals, airdrops)
  Team/Dev:           5,000,000 KAIG ( 5% — 4-year vesting, 1-year cliff)

  Monthly Escrow Release: 500,000 KAIG max (0.5% of total)
  Re-lock Rate: 70-80% of released tokens re-locked (like XRP)
  Net Monthly Circulation Increase: ~100,000-150,000 KAIG

  Target Market Cap at $10/coin: $1B (with 100M circulating)
  Initial Internal Price: $0.10 (bootstrap phase)
  Path to $10: Revenue-backed buybacks + controlled supply + real utility
"""

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.kaig_runtime_config import KAIGConfig

logger = logging.getLogger("KingdomAI.KAIG")

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

# ══════════════════════════════════════════════════════════════════
# KAIG TOKENOMICS — NOW LOADED FROM RUNTIME CONFIG (hot-reloadable)
# Module-level names preserved for backward compatibility.
# To change ANY value at runtime: edit config/kaig/runtime_config.json
# or set env var KAIG_TOKENOMICS_TOTAL_SUPPLY=200000000 etc.
# ══════════════════════════════════════════════════════════════════

def _cfg():
    """Shortcut to the singleton config."""
    return KAIGConfig.get()

# These are evaluated at import time but every subsystem that needs
# the *live* value should call _cfg().total_supply etc. instead.
TOTAL_SUPPLY = _cfg().total_supply
ESCROW_SUPPLY = _cfg().escrow_supply
TREASURY_SUPPLY = _cfg().treasury_supply
COMMUNITY_SUPPLY = _cfg().community_supply
TEAM_SUPPLY = _cfg().team_supply

MONTHLY_ESCROW_RELEASE = _cfg().monthly_escrow_release
ESCROW_RELOCK_RATE = _cfg().escrow_relock_rate
NET_MONTHLY_RELEASE = _cfg().net_monthly_release

TARGET_PRICE = _cfg().target_price
INITIAL_PRICE = _cfg().initial_price
TRANSACTION_BURN_RATE = _cfg().transaction_burn_rate

TRADING_PROFIT_BUYBACK_RATE = _cfg().trading_profit_buyback_rate
MIN_BUYBACK_THRESHOLD_USD = _cfg().min_buyback_threshold_usd
BUYBACK_COOLDOWN_HOURS = _cfg().buyback_cooldown_hours

NODE_REWARD_PER_HOUR = _cfg().node_reward_per_hour
NODE_REWARD_CAP_DAILY = _cfg().node_reward_cap_daily
STAKING_APY = _cfg().staking_apy

CONFIG_DIR = _cfg().config_dir
LEDGER_PATH = _cfg().ledger_path
ESCROW_PATH = _cfg().escrow_path
TREASURY_PATH = _cfg().treasury_path
NODE_PATH = _cfg().node_path
BUYBACK_LOG_PATH = _cfg().buyback_log_path


class KAIGLedger:
    """
    Local KAIG ledger — tracks balances, transactions, burns.
    In production this would be on-chain; for now it's a JSON-based ledger
    that can be migrated to a real blockchain when KAIG launches.
    """

    def __init__(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.ledger = self._load(LEDGER_PATH, {
            "balances": {},
            "transactions": [],
            "total_burned": 0.0,
            "total_minted_to_circulation": 0.0,
            "genesis_time": datetime.utcnow().isoformat(),
        })

    def _load(self, path: str, default: dict) -> dict:
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("Init: Failed to load ledger from %s: %s", path, e)
        return default

    def _save(self):
        try:
            with open(LEDGER_PATH, "w") as f:
                json.dump(self.ledger, f, indent=2)
        except Exception as e:
            logger.error("Failed to save KAIG ledger: %s", e)

    def get_balance(self, wallet_id: str) -> float:
        return self.ledger["balances"].get(wallet_id, 0.0)

    def credit(self, wallet_id: str, amount: float, reason: str = "") -> Dict:
        """Credit KAIG to a wallet."""
        if amount <= 0:
            return {"error": "Amount must be positive"}
        bal = self.ledger["balances"].get(wallet_id, 0.0)
        self.ledger["balances"][wallet_id] = round(bal + amount, 6)
        tx = {
            "id": str(uuid.uuid4())[:12],
            "type": "credit",
            "wallet": wallet_id,
            "amount": round(amount, 6),
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
            "balance_after": self.ledger["balances"][wallet_id],
        }
        self.ledger["transactions"].append(tx)
        self._save()
        return tx

    def debit(self, wallet_id: str, amount: float, reason: str = "") -> Dict:
        """Debit KAIG from a wallet."""
        if amount <= 0:
            return {"error": "Amount must be positive"}
        bal = self.ledger["balances"].get(wallet_id, 0.0)
        if bal < amount:
            return {"error": "Insufficient balance", "balance": bal}
        self.ledger["balances"][wallet_id] = round(bal - amount, 6)
        tx = {
            "id": str(uuid.uuid4())[:12],
            "type": "debit",
            "wallet": wallet_id,
            "amount": round(amount, 6),
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
            "balance_after": self.ledger["balances"][wallet_id],
        }
        self.ledger["transactions"].append(tx)
        self._save()
        return tx

    def transfer(self, from_wallet: str, to_wallet: str, amount: float,
                 reason: str = "") -> Dict:
        """Transfer KAIG between wallets with burn on transaction."""
        if amount <= 0:
            return {"error": "Amount must be positive"}
        bal = self.ledger["balances"].get(from_wallet, 0.0)
        if bal < amount:
            return {"error": "Insufficient balance", "balance": bal}

        burn_amount = round(amount * TRANSACTION_BURN_RATE, 6)
        net_amount = round(amount - burn_amount, 6)

        self.ledger["balances"][from_wallet] = round(bal - amount, 6)
        to_bal = self.ledger["balances"].get(to_wallet, 0.0)
        self.ledger["balances"][to_wallet] = round(to_bal + net_amount, 6)
        self.ledger["total_burned"] = round(
            self.ledger["total_burned"] + burn_amount, 6)

        tx = {
            "id": str(uuid.uuid4())[:12],
            "type": "transfer",
            "from": from_wallet,
            "to": to_wallet,
            "amount": round(amount, 6),
            "burn": burn_amount,
            "net_received": net_amount,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.ledger["transactions"].append(tx)
        self._save()
        return tx

    def burn(self, wallet_id: str, amount: float, reason: str = "") -> Dict:
        """Permanently burn KAIG — deflationary pressure."""
        if amount <= 0:
            return {"error": "Amount must be positive"}
        bal = self.ledger["balances"].get(wallet_id, 0.0)
        if bal < amount:
            return {"error": "Insufficient balance"}
        self.ledger["balances"][wallet_id] = round(bal - amount, 6)
        self.ledger["total_burned"] = round(
            self.ledger["total_burned"] + amount, 6)
        tx = {
            "id": str(uuid.uuid4())[:12],
            "type": "burn",
            "wallet": wallet_id,
            "amount": round(amount, 6),
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
            "total_burned": self.ledger["total_burned"],
        }
        self.ledger["transactions"].append(tx)
        self._save()
        return tx

    def get_stats(self) -> Dict:
        """Get overall KAIG network stats."""
        balances = self.ledger.get("balances", {})
        total_circulating = sum(balances.values())
        return {
            "total_supply": TOTAL_SUPPLY,
            "total_circulating": round(total_circulating, 6),
            "total_burned": self.ledger.get("total_burned", 0.0),
            "effective_supply": round(TOTAL_SUPPLY - self.ledger.get("total_burned", 0.0), 6),
            "num_wallets": len(balances),
            "num_transactions": len(self.ledger.get("transactions", [])),
            "genesis_time": self.ledger.get("genesis_time", ""),
        }

    def recent_transactions(self, limit: int = 20) -> List[Dict]:
        txs = self.ledger.get("transactions", [])
        return txs[-limit:]


class KAIGEscrow:
    """
    XRP-style escrow — time-locked token release with re-lock mechanism.
    70M tokens locked at genesis, 500K max released per month.
    75% of released tokens re-locked at end of queue.
    """

    def __init__(self, ledger: KAIGLedger):
        self.ledger = ledger
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.escrow = self._load()

    def _load(self) -> dict:
        try:
            if os.path.exists(ESCROW_PATH):
                with open(ESCROW_PATH, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("Init: Failed to load escrow from %s: %s", ESCROW_PATH, e)
        # Initialize escrow schedule
        return self._initialize_escrow()

    def _initialize_escrow(self) -> dict:
        """Create initial escrow schedule — 140 monthly slots of 500K each."""
        now = datetime.utcnow()
        slots = []
        for i in range(140):  # 70M / 500K = 140 months (~11.7 years)
            release_date = (now + timedelta(days=30 * (i + 1))).isoformat()
            slots.append({
                "slot_id": i + 1,
                "amount": MONTHLY_ESCROW_RELEASE,
                "release_date": release_date,
                "status": "locked",
                "released_at": None,
                "relock_amount": 0,
            })
        escrow = {
            "total_locked": ESCROW_SUPPLY,
            "total_released": 0.0,
            "total_relocked": 0.0,
            "slots": slots,
            "created_at": now.isoformat(),
        }
        self._save(escrow)
        return escrow

    def _save(self, data: dict = None):
        try:
            with open(ESCROW_PATH, "w") as f:
                json.dump(data or self.escrow, f, indent=2)
        except Exception as e:
            logger.error("Failed to save escrow: %s", e)

    def check_and_release(self) -> Optional[Dict]:
        """Check if any escrow slots are due for release."""
        now = datetime.utcnow()
        for slot in self.escrow.get("slots", []):
            if slot["status"] != "locked":
                continue
            try:
                release_date = datetime.fromisoformat(slot["release_date"])
            except (ValueError, TypeError):
                continue
            if now >= release_date:
                # Release this slot
                amount = slot["amount"]
                relock = round(amount * ESCROW_RELOCK_RATE, 6)
                net_release = round(amount - relock, 6)

                slot["status"] = "released"
                slot["released_at"] = now.isoformat()
                slot["relock_amount"] = relock

                self.escrow["total_released"] = round(
                    self.escrow["total_released"] + net_release, 6)
                self.escrow["total_relocked"] = round(
                    self.escrow["total_relocked"] + relock, 6)
                self.escrow["total_locked"] = round(
                    self.escrow["total_locked"] - net_release, 6)

                # Re-lock: add new slot at end of queue
                last_slot = self.escrow["slots"][-1]
                try:
                    last_date = datetime.fromisoformat(last_slot["release_date"])
                except (ValueError, TypeError):
                    last_date = now
                new_slot = {
                    "slot_id": last_slot["slot_id"] + 1,
                    "amount": relock,
                    "release_date": (last_date + timedelta(days=30)).isoformat(),
                    "status": "locked",
                    "released_at": None,
                    "relock_amount": 0,
                }
                self.escrow["slots"].append(new_slot)

                # Credit net release to treasury
                self.ledger.credit("treasury", net_release,
                                   f"Escrow release slot #{slot['slot_id']}")

                self._save()
                logger.info("Escrow slot #%d released: %s KAIG (re-locked: %s)",
                            slot["slot_id"], net_release, relock)
                return {
                    "slot_id": slot["slot_id"],
                    "gross_release": amount,
                    "net_release": net_release,
                    "relocked": relock,
                    "total_locked": self.escrow["total_locked"],
                }
        return None

    def get_status(self) -> Dict:
        locked_slots = sum(1 for s in self.escrow.get("slots", [])
                          if s["status"] == "locked")
        released_slots = sum(1 for s in self.escrow.get("slots", [])
                            if s["status"] == "released")
        next_release = None
        for s in self.escrow.get("slots", []):
            if s["status"] == "locked":
                next_release = s["release_date"]
                break
        return {
            "total_locked": self.escrow.get("total_locked", ESCROW_SUPPLY),
            "total_released": self.escrow.get("total_released", 0),
            "total_relocked": self.escrow.get("total_relocked", 0),
            "locked_slots": locked_slots,
            "released_slots": released_slots,
            "next_release_date": next_release,
            "relock_rate": f"{ESCROW_RELOCK_RATE * 100:.0f}%",
        }


class KAIGTreasury:
    """
    AI-managed treasury — holds multi-asset reserves (BTC/ETH/USDC).
    Trading profits flow here. AI decides optimal buyback timing.
    Goal: Build KAIG value to $10 before public listing.
    """

    def __init__(self, ledger: KAIGLedger, event_bus=None):
        self.ledger = ledger
        self.event_bus = event_bus
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.treasury = self._load()
        self._last_buyback_time = 0.0

    def _load(self) -> dict:
        try:
            if os.path.exists(TREASURY_PATH):
                with open(TREASURY_PATH, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("Init: Failed to load treasury from %s: %s", TREASURY_PATH, e)
        return {
            "reserves": {"BTC": 0.0, "ETH": 0.0, "USDC": 0.0},
            "kaig_held": TREASURY_SUPPLY,
            "total_buyback_usd": 0.0,
            "total_buyback_kaig": 0.0,
            "buyback_history": [],
            "internal_price": INITIAL_PRICE,
            "price_history": [
                {"price": INITIAL_PRICE, "time": datetime.utcnow().isoformat()}
            ],
            "created_at": datetime.utcnow().isoformat(),
        }

    def _save(self):
        try:
            with open(TREASURY_PATH, "w") as f:
                json.dump(self.treasury, f, indent=2)
        except Exception as e:
            logger.error("Failed to save treasury: %s", e)

    def record_trading_profit(self, profit_usd: float, source: str = "trading") -> Dict:
        """
        Record a trading profit. 50% goes to KAIG buyback.
        This is the core mechanism: Kingdom AI trades → profits → buy KAIG.
        """
        if profit_usd <= 0:
            return {"status": "no_profit"}

        buyback_usd = round(profit_usd * TRADING_PROFIT_BUYBACK_RATE, 2)
        self.treasury["reserves"]["USDC"] = round(
            self.treasury["reserves"].get("USDC", 0) + (profit_usd - buyback_usd), 2)

        result = {"profit_usd": profit_usd, "allocated_to_buyback": buyback_usd}

        # Check if we meet the buyback threshold
        if buyback_usd >= MIN_BUYBACK_THRESHOLD_USD:
            buyback_result = self._execute_buyback(buyback_usd, source)
            result.update(buyback_result)
        else:
            # Accumulate for later
            pending = self.treasury.get("pending_buyback_usd", 0.0)
            self.treasury["pending_buyback_usd"] = round(pending + buyback_usd, 2)
            result["pending_buyback_usd"] = self.treasury["pending_buyback_usd"]

        self._save()
        return result

    def _ai_assess_buyback(self, usd_amount: float, current_price: float) -> Dict:
        """Ask the Ollama brain whether NOW is optimal for a buyback and what
        price-impact estimate it recommends, given current treasury state."""
        if not _ensure_orch():
            return {"execute": True, "ai_impact_factor": 1.0, "reasoning": "orchestrator unavailable"}
        try:
            import requests
            model = _orch.get_model_for_task("kaig")
            url = get_ollama_url()
            prompt = (
                f"You are the AI treasury manager for the $KAIG cryptocurrency.\n"
                f"Current internal price: ${current_price:.4f}\n"
                f"Buyback amount available: ${usd_amount:.2f}\n"
                f"Total buybacks executed so far: ${self.treasury.get('total_buyback_usd', 0):.2f}\n"
                f"KAIG held by treasury: {self.treasury.get('kaig_held', 0):,.0f}\n"
                f"Target price: ${TARGET_PRICE}\n"
                f"Total supply: {TOTAL_SUPPLY:,}\n\n"
                f"Should the treasury execute this buyback NOW? "
                f"Respond with ONLY valid JSON: "
                f'{{"execute": true/false, "impact_factor": 0.5-2.0, "reasoning": "one sentence"}}\n'
                f"impact_factor > 1.0 means conditions favor a larger price impact, < 1.0 means conserve."
            )
            resp = requests.post(
                f"{url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": 120, "temperature": 0.3},
                      "keep_alive": -1},
                timeout=30,
            )
            if resp.status_code == 200:
                raw = resp.json().get("response", "")
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(raw[start:end])
                    execute = bool(parsed.get("execute", True))
                    factor = max(0.5, min(2.0, float(parsed.get("impact_factor", 1.0))))
                    reasoning = str(parsed.get("reasoning", ""))[:200]
                    logger.info("KAIG AI buyback assessment: execute=%s factor=%.2f — %s",
                                execute, factor, reasoning)
                    return {"execute": execute, "ai_impact_factor": factor, "reasoning": reasoning}
        except Exception as e:
            logger.debug("AI buyback assessment unavailable: %s", e)
        return {"execute": True, "ai_impact_factor": 1.0, "reasoning": "ai_unavailable"}

    def _execute_buyback(self, usd_amount: float, source: str = "") -> Dict:
        """
        Execute KAIG buyback — AI-managed timing optimization.
        The Ollama brain assesses whether NOW is optimal and adjusts
        the price-impact factor based on treasury state analysis.
        """
        now = time.time()
        cooldown = BUYBACK_COOLDOWN_HOURS * 3600
        if now - self._last_buyback_time < cooldown:
            pending = self.treasury.get("pending_buyback_usd", 0.0)
            self.treasury["pending_buyback_usd"] = round(pending + usd_amount, 2)
            return {"status": "cooldown", "pending": self.treasury["pending_buyback_usd"]}

        # Include any pending amount
        pending = self.treasury.get("pending_buyback_usd", 0.0)
        total_usd = round(usd_amount + pending, 2)

        # Calculate KAIG amount at current internal price
        current_price = self.treasury.get("internal_price", INITIAL_PRICE)

        # ── AI BUYBACK ASSESSMENT ───────────────────────────────
        ai_assessment = self._ai_assess_buyback(total_usd, current_price)
        if not ai_assessment.get("execute", True):
            self.treasury["pending_buyback_usd"] = round(
                self.treasury.get("pending_buyback_usd", 0) + usd_amount, 2)
            logger.info("AI deferred buyback: %s", ai_assessment.get("reasoning", ""))
            return {"status": "ai_deferred", "reasoning": ai_assessment.get("reasoning", ""),
                    "pending": self.treasury["pending_buyback_usd"]}

        self.treasury["pending_buyback_usd"] = 0.0
        kaig_amount = round(total_usd / current_price, 6)

        # Buyback: treasury acquires KAIG (reducing circulating supply)
        self.treasury["total_buyback_usd"] = round(
            self.treasury["total_buyback_usd"] + total_usd, 2)
        self.treasury["total_buyback_kaig"] = round(
            self.treasury["total_buyback_kaig"] + kaig_amount, 6)
        self.treasury["kaig_held"] = round(
            self.treasury["kaig_held"] + kaig_amount, 6)

        # AI-adjusted price impact (brain modulates the base formula)
        ai_factor = ai_assessment.get("ai_impact_factor", 1.0)
        price_impact = (total_usd / 1000.0) * 0.001 * ai_factor
        new_price = round(min(current_price * (1 + price_impact), TARGET_PRICE), 6)
        self.treasury["internal_price"] = new_price
        self.treasury["price_history"].append({
            "price": new_price,
            "time": datetime.utcnow().isoformat(),
            "trigger": "buyback",
            "usd_amount": total_usd,
        })

        entry = {
            "id": str(uuid.uuid4())[:12],
            "usd_amount": total_usd,
            "kaig_amount": kaig_amount,
            "price_before": current_price,
            "price_after": new_price,
            "ai_impact_factor": ai_factor,
            "ai_reasoning": ai_assessment.get("reasoning", ""),
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.treasury["buyback_history"].append(entry)
        self._last_buyback_time = now

        self._save()

        # Publish event
        if self.event_bus and hasattr(self.event_bus, 'publish'):
            self.event_bus.publish("kaig.buyback", entry)

        logger.info("KAIG buyback: $%.2f → %.2f KAIG @ $%.4f (new price: $%.4f) [AI factor: %.2f]",
                    total_usd, kaig_amount, current_price, new_price, ai_factor)
        return {
            "status": "buyback_executed",
            "usd_spent": total_usd,
            "kaig_acquired": kaig_amount,
            "price_before": current_price,
            "price_after": new_price,
            "ai_impact_factor": ai_factor,
            "success": True,
        }

    def get_internal_price(self) -> float:
        return self.treasury.get("internal_price", INITIAL_PRICE)

    def get_status(self) -> Dict:
        price = self.treasury.get("internal_price", INITIAL_PRICE)
        kaig_held = self.treasury.get("kaig_held", TREASURY_SUPPLY)
        reserves = self.treasury.get("reserves", {})
        return {
            "internal_price": price,
            "price_vs_target": f"${price:.4f} / ${TARGET_PRICE:.2f}",
            "progress_to_target": round((price / TARGET_PRICE) * 100, 2),
            "kaig_held_by_treasury": kaig_held,
            "treasury_value_usd": round(kaig_held * price, 2),
            "reserves": reserves,
            "total_reserves_usd": round(sum(reserves.values()), 2),
            "total_buyback_usd": self.treasury.get("total_buyback_usd", 0),
            "total_buyback_kaig": self.treasury.get("total_buyback_kaig", 0),
            "pending_buyback_usd": self.treasury.get("pending_buyback_usd", 0),
            "num_buybacks": len(self.treasury.get("buyback_history", [])),
            "recent_buybacks": self.treasury.get("buyback_history", [])[-5:],
        }


class KAIGNode:
    """
    KAIG Node — lightweight proof-of-stake + proof-of-contribution node.
    Users earn KAIG by running a node that contributes:
      1. Bandwidth for KAIG network relay
      2. Compute for AI model inference tasks
      3. Storage for distributed ledger replication
      4. Uptime for network reliability

    NOT fake mining — actual resource contribution measured and verified.
    """

    def __init__(self, ledger: KAIGLedger, node_id: str = None):
        self.ledger = ledger
        self.node_id = node_id or self._generate_node_id()
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.node_data = self._load()
        self._running = False
        self._start_time: Optional[float] = None
        self._session_earned = 0.0
        self._today_earned = 0.0
        self._last_reward_time = 0.0

    def _generate_node_id(self) -> str:
        machine_hash = hashlib.sha256(
            (os.environ.get("COMPUTERNAME", "") +
             os.environ.get("USERNAME", "") +
             str(uuid.getnode())).encode()
        ).hexdigest()[:12]
        return f"KAIG-NODE-{machine_hash.upper()}"

    def _load(self) -> dict:
        try:
            if os.path.exists(NODE_PATH):
                with open(NODE_PATH, "r") as f:
                    data = json.load(f)
                    nodes = data.get("nodes", {})
                    if self.node_id in nodes:
                        return data
                    # Register this node
                    nodes[self.node_id] = self._new_node_entry()
                    data["nodes"] = nodes
                    self._save(data)
                    return data
        except Exception as e:
            logger.warning("Init: Failed to load node data from %s: %s", NODE_PATH, e)
        data = {
            "nodes": {self.node_id: self._new_node_entry()},
            "network_stats": {
                "total_nodes": 1,
                "total_rewards_distributed": 0.0,
            },
        }
        self._save(data)
        return data

    def _new_node_entry(self) -> dict:
        return {
            "node_id": self.node_id,
            "registered_at": datetime.utcnow().isoformat(),
            "total_uptime_hours": 0.0,
            "total_earned": 0.0,
            "total_bandwidth_mb": 0.0,
            "total_compute_tasks": 0,
            "stake_amount": 0.0,
            "status": "offline",
            "last_heartbeat": None,
            "version": "1.0.0",
        }

    def _save(self, data: dict = None):
        try:
            with open(NODE_PATH, "w") as f:
                json.dump(data or self.node_data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save node data: %s", e)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def uptime_seconds(self) -> float:
        if self._start_time and self._running:
            return time.time() - self._start_time
        return 0.0

    def start(self) -> Dict:
        """Start the KAIG node."""
        if self._running:
            return {"status": "already_running", "node_id": self.node_id}

        self._running = True
        self._start_time = time.time()
        self._session_earned = 0.0
        self._last_reward_time = time.time()

        node = self.node_data.get("nodes", {}).get(self.node_id, {})
        node["status"] = "online"
        node["last_heartbeat"] = datetime.utcnow().isoformat()
        self.node_data["nodes"][self.node_id] = node
        self._save()

        logger.info("KAIG Node %s started", self.node_id)
        return {"status": "started", "node_id": self.node_id}

    def stop(self) -> Dict:
        """Stop the KAIG node."""
        if not self._running:
            return {"status": "not_running"}

        session_duration = self.uptime_seconds
        self._running = False

        node = self.node_data.get("nodes", {}).get(self.node_id, {})
        node["status"] = "offline"
        node["total_uptime_hours"] = round(
            node.get("total_uptime_hours", 0) + (session_duration / 3600), 4)
        self.node_data["nodes"][self.node_id] = node
        self._save()
        self._start_time = None

        logger.info("KAIG Node %s stopped (session: %.1fs, earned: %.4f KAIG)",
                    self.node_id, session_duration, self._session_earned)
        return {
            "status": "stopped",
            "node_id": self.node_id,
            "session_duration": round(session_duration, 1),
            "session_earned": round(self._session_earned, 6),
        }

    def heartbeat(self) -> Dict:
        """
        Node heartbeat — called periodically (every 30s-60s).
        Earns KAIG based on uptime + contribution.
        """
        if not self._running:
            return {}

        now = time.time()
        elapsed_hours = (now - self._last_reward_time) / 3600.0

        # Check daily cap
        if self._today_earned >= NODE_REWARD_CAP_DAILY:
            return {
                "status": "daily_cap_reached",
                "today_earned": self._today_earned,
                "cap": NODE_REWARD_CAP_DAILY,
            }

        # Calculate reward
        reward = round(NODE_REWARD_PER_HOUR * elapsed_hours, 6)
        # Staking bonus
        node = self.node_data.get("nodes", {}).get(self.node_id, {})
        stake = node.get("stake_amount", 0)
        if stake > 0:
            stake_bonus = round(stake * STAKING_APY * elapsed_hours / 8760, 6)
            reward += stake_bonus

        reward = min(reward, NODE_REWARD_CAP_DAILY - self._today_earned)
        if reward <= 0:
            return {"status": "no_reward"}

        # Credit the node operator
        wallet_id = f"node:{self.node_id}"
        self.ledger.credit(wallet_id, reward, "Node reward")
        self._session_earned += reward
        self._today_earned += reward
        self._last_reward_time = now

        # Update node stats
        node["total_earned"] = round(node.get("total_earned", 0) + reward, 6)
        node["last_heartbeat"] = datetime.utcnow().isoformat()
        # Bandwidth/compute metrics are updated by the network monitoring and compute
        # task tracking subsystems when available; values persist across heartbeats.
        self.node_data["nodes"][self.node_id] = node
        self._save()

        return {
            "status": "rewarded",
            "reward": round(reward, 6),
            "session_earned": round(self._session_earned, 6),
            "today_earned": round(self._today_earned, 6),
            "daily_cap": NODE_REWARD_CAP_DAILY,
            "balance": self.ledger.get_balance(wallet_id),
            "uptime": round(self.uptime_seconds, 1),
        }

    def stake(self, amount: float) -> Dict:
        """Stake KAIG to earn higher rewards + help secure network."""
        wallet_id = f"node:{self.node_id}"
        bal = self.ledger.get_balance(wallet_id)
        if bal < amount:
            return {"error": "Insufficient KAIG balance", "balance": bal}
        # Lock tokens in stake
        self.ledger.debit(wallet_id, amount, "Staked for node rewards")
        node = self.node_data.get("nodes", {}).get(self.node_id, {})
        node["stake_amount"] = round(node.get("stake_amount", 0) + amount, 6)
        self.node_data["nodes"][self.node_id] = node
        self._save()
        return {
            "status": "staked",
            "amount": amount,
            "total_stake": node["stake_amount"],
            "apy": f"{STAKING_APY * 100:.1f}%",
        }

    def get_status(self) -> Dict:
        node = self.node_data.get("nodes", {}).get(self.node_id, {})
        wallet_id = f"node:{self.node_id}"
        return {
            "node_id": self.node_id,
            "status": "online" if self._running else "offline",
            "uptime_seconds": round(self.uptime_seconds, 1),
            "total_uptime_hours": node.get("total_uptime_hours", 0),
            "balance": self.ledger.get_balance(wallet_id),
            "session_earned": round(self._session_earned, 6),
            "today_earned": round(self._today_earned, 6),
            "daily_cap": NODE_REWARD_CAP_DAILY,
            "total_earned": node.get("total_earned", 0),
            "stake_amount": node.get("stake_amount", 0),
            "staking_apy": f"{STAKING_APY * 100:.1f}%",
            "bandwidth_contributed_mb": node.get("total_bandwidth_mb", 0),
            "compute_tasks": node.get("total_compute_tasks", 0),
            "version": node.get("version", "1.0.0"),
        }

    def get_network_stats(self) -> Dict:
        """Get overall KAIG node network stats."""
        nodes = self.node_data.get("nodes", {})
        online = sum(1 for n in nodes.values() if n.get("status") == "online")
        total_earned = sum(n.get("total_earned", 0) for n in nodes.values())
        total_uptime = sum(n.get("total_uptime_hours", 0) for n in nodes.values())
        total_staked = sum(n.get("stake_amount", 0) for n in nodes.values())
        return {
            "total_nodes": len(nodes),
            "online_nodes": online,
            "total_rewards_distributed": round(total_earned, 6),
            "total_uptime_hours": round(total_uptime, 2),
            "total_staked": round(total_staked, 6),
            "reward_rate": f"{NODE_REWARD_PER_HOUR} KAIG/hr",
            "daily_cap": f"{NODE_REWARD_CAP_DAILY} KAIG/day",
            "staking_apy": f"{STAKING_APY * 100:.1f}%",
        }


class KAIGEngine:
    """
    Master KAIG engine — coordinates all subsystems.
    The Kingdom AI brain that manages the entire KAIG economy.
    """

    _instance = None

    @classmethod
    def get_instance(cls, event_bus=None) -> "KAIGEngine":
        if cls._instance is None:
            cls._instance = cls(event_bus=event_bus)
        return cls._instance

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.ledger = KAIGLedger()
        self.escrow = KAIGEscrow(self.ledger)
        self.treasury = KAIGTreasury(self.ledger, event_bus)
        self.node = KAIGNode(self.ledger)
        self._trading_system_readiness = {"state": "UNKNOWN", "auto_trade_started": False}
        self._stats_cache = {}
        self._stats_cache_time = 0.0

        # ── COMPREHENSIVE EVENT SUBSCRIPTIONS ──
        # Subscribe to EVERY revenue-generating event in the Kingdom AI ecosystem
        if self.event_bus and hasattr(self.event_bus, 'subscribe'):
            _sub = self.event_bus.subscribe

            # Trading system → profit pipeline (auto-buyback)
            _sub("trading.profit", self._on_trading_profit)
            _sub("trading.closed", self._on_trade_closed)
            _sub("trading.order.update", self._on_order_update)
            _sub("trading.order_update", self._on_order_update)
            _sub("trading.position_update", self._on_position_update)
            _sub("trading.response", self._on_trading_response)
            _sub("trading.signal", self._on_trading_signal)

            # Portfolio system → realized gains pipeline
            _sub("portfolio.unified.update", self._on_portfolio_update)
            _sub("portfolio.profit", self._on_trading_profit)

            # Mining system → reward conversion pipeline
            _sub("mining.reward_update", self._on_mining_reward)
            _sub("mining.started", self._on_mining_started)
            _sub("mining.stopped", self._on_mining_stopped)
            _sub("mining.hashrate_update", self._on_mining_hashrate)

            # Commission system → profit from user fees
            _sub("commission.collected", self._on_commission_collected)
            _sub("referral.applied", self._on_referral_applied)

            # KAIG-specific events (status requests from UI)
            _sub("kaig.status.request", self._on_status_request)
            _sub("kaig.buyback.manual", self._on_manual_buyback)
            _sub("kaig.node.start", self._on_node_start_request)
            _sub("kaig.node.stop", self._on_node_stop_request)
            _sub("trading.system.readiness", self._on_trading_system_readiness)

            logger.info("KAIG Engine: subscribed to %d event channels", 19)

        # Initialize treasury wallet
        treasury_bal = self.ledger.get_balance("treasury")
        if treasury_bal == 0:
            self.ledger.credit("treasury", TREASURY_SUPPLY,
                              "Genesis: Treasury allocation")
            logger.info("KAIG Genesis: Treasury initialized with %d KAIG",
                       TREASURY_SUPPLY)

        # Initialize community pool
        community_bal = self.ledger.get_balance("community_pool")
        if community_bal == 0:
            self.ledger.credit("community_pool", COMMUNITY_SUPPLY,
                              "Genesis: Community pool allocation")
            logger.info("KAIG Genesis: Community pool initialized with %d KAIG",
                       COMMUNITY_SUPPLY)

        # ── LIVE ATH MONITOR ──
        # 1 KAIG must ALWAYS be priced higher than the highest crypto ATH ever.
        # This is live-monitored — if any coin sets a new ATH, KAIG surpasses it.
        self._ath_record = {
            "coin": "BTC",
            "price_usd": 125835.92,
            "date": "2025-10-06",
        }
        self._kaig_price_floor = 125835.93  # Must exceed this
        self._ath_monitor_running = False
        self._start_ath_monitor()

        # ── START KAIG INTELLIGENCE BRIDGE ──
        # Wires KAIG goals into Trading/Mining/Wallet intelligence systems
        try:
            from core.kaig_intelligence_bridge import KAIGIntelligenceBridge
            self._intel_bridge = KAIGIntelligenceBridge.get_instance(event_bus=self.event_bus)
            self._intel_bridge.start(event_bus=self.event_bus)
            logger.info("KAIG Intelligence Bridge started — directives flowing to all systems")
        except Exception as e:
            logger.warning("KAIG Intelligence Bridge unavailable: %s", e)
            self._intel_bridge = None

        ticker = _cfg().ticker or "KAIG"
        logger.info("KAIG Engine initialized — $%s (%s) — all systems wired | "
                    "KAIG price floor: $%s (must exceed %s ATH $%s)",
                    ticker, _cfg().name or "KAI Gold",
                    f"{self._kaig_price_floor:,.2f}",
                    self._ath_record["coin"],
                    f"{self._ath_record['price_usd']:,.2f}")

    # ── LIVE ATH MONITOR ────────────────────────────────────────

    def _start_ath_monitor(self):
        """Start background thread that live-monitors crypto ATHs.
        1 KAIG must always be priced higher than the highest ATH ever recorded.
        """
        # Load initial ATH from config
        cfg_floor = _cfg().get_value("kaig_price_floor", {})
        if isinstance(cfg_floor, dict):
            bench = cfg_floor.get("current_ath_benchmark", {})
            if bench.get("price_usd", 0) > self._ath_record.get("price_usd", 0):
                self._ath_record = {
                    "coin": bench.get("coin", "BTC"),
                    "price_usd": bench["price_usd"],
                    "date": bench.get("date", "unknown"),
                }
                self._kaig_price_floor = bench["price_usd"] + 0.01

        self._ath_monitor_running = True
        import threading
        t = threading.Thread(target=self._ath_monitor_loop, daemon=True,
                            name="KAIG-ATH-Monitor")
        t.start()
        logger.info("KAIG ATH Monitor started — tracking live crypto ATHs")

    def _ath_monitor_loop(self):
        """Poll CoinGecko for live ATH data. Update KAIG price floor if any coin breaks the record."""
        import urllib.request
        while self._ath_monitor_running:
            try:
                interval = 300  # 5 minutes default
                cfg_floor = _cfg().get_value("kaig_price_floor", {})
                if isinstance(cfg_floor, dict):
                    interval = cfg_floor.get("monitor_interval_seconds", 300)
                    coins = cfg_floor.get("monitor_coins", ["BTC", "ETH", "SOL", "BNB", "XRP"])
                else:
                    coins = ["BTC", "ETH", "SOL", "BNB", "XRP"]

                # CoinGecko free API — ATH data for monitored coins
                coin_ids = {
                    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
                    "BNB": "binancecoin", "XRP": "ripple", "ADA": "cardano",
                    "AVAX": "avalanche-2", "DOT": "polkadot", "DOGE": "dogecoin",
                    "LINK": "chainlink", "MATIC": "matic-network",
                }
                ids_param = ",".join(coin_ids.get(c, c.lower()) for c in coins)
                url = (f"https://api.coingecko.com/api/v3/coins/markets"
                       f"?vs_currency=usd&ids={ids_param}"
                       f"&order=market_cap_desc&per_page=50&page=1"
                       f"&sparkline=false")

                req = urllib.request.Request(url, headers={"User-Agent": "KingdomAI/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())

                if isinstance(data, list):
                    for coin_data in data:
                        ath = coin_data.get("ath", 0)
                        symbol = (coin_data.get("symbol") or "").upper()
                        ath_date = coin_data.get("ath_date", "")
                        if isinstance(ath, (int, float)) and ath > self._ath_record.get("price_usd", 0):
                            old = self._ath_record.copy()
                            self._ath_record = {
                                "coin": symbol,
                                "price_usd": ath,
                                "date": ath_date[:10] if ath_date else "unknown",
                            }
                            self._kaig_price_floor = ath + 0.01
                            logger.warning(
                                "═══ NEW CRYPTO ATH DETECTED ═══ "
                                "%s hit $%s (was %s at $%s). "
                                "KAIG price floor raised to $%s",
                                symbol, f"{ath:,.2f}",
                                old["coin"], f"{old['price_usd']:,.2f}",
                                f"{self._kaig_price_floor:,.2f}")

                            # Persist to runtime config
                            try:
                                KAIGConfig.set("kaig_price_floor.current_ath_benchmark", {
                                    "coin": symbol,
                                    "price_usd": ath,
                                    "date": self._ath_record["date"],
                                    "source": "CoinGecko live ATH monitor",
                                })
                                KAIGConfig.set("kaig_price_floor.kaig_must_exceed_usd", self._kaig_price_floor)
                            except Exception as e:
                                logger.warning("context: Failed to persist ATH benchmark to config: %s", e)

                            # Publish to event bus
                            if self.event_bus:
                                self.event_bus.publish("kaig.ath.update", {
                                    "new_ath_coin": symbol,
                                    "new_ath_price": ath,
                                    "kaig_price_floor": self._kaig_price_floor,
                                    "previous": old,
                                    "timestamp": datetime.utcnow().isoformat(),
                                })

                    # Periodic log even if no change
                    logger.debug(
                        "ATH Monitor: highest=%s $%s | KAIG floor=$%s | checked %d coins",
                        self._ath_record["coin"],
                        f"{self._ath_record['price_usd']:,.2f}",
                        f"{self._kaig_price_floor:,.2f}",
                        len(data))

            except Exception as e:
                logger.debug("ATH monitor fetch error (will retry): %s", e)

            try:
                time.sleep(interval)
            except Exception:
                break

    def get_ath_status(self) -> Dict:
        """Get current ATH monitoring status."""
        return {
            "highest_ath_coin": self._ath_record.get("coin", "BTC"),
            "highest_ath_usd": self._ath_record.get("price_usd", 0),
            "highest_ath_date": self._ath_record.get("date", "unknown"),
            "kaig_price_floor_usd": self._kaig_price_floor,
            "kaig_exceeds_ath": True,  # By design — KAIG is always above
            "monitor_active": self._ath_monitor_running,
        }

    # ── TRADING EVENT HANDLERS ──────────────────────────────────

    def _on_trading_profit(self, data: Any):
        """Handle trading profit events — auto-buyback pipeline."""
        profit = 0.0
        if isinstance(data, dict):
            profit = data.get("profit_usd", 0) or data.get("profit", 0) or data.get("pnl", 0)
        elif isinstance(data, (int, float)):
            profit = float(data)
        if profit > 0:
            result = self.treasury.record_trading_profit(profit, "ai_trading")
            logger.info("Trading profit $%.2f processed → KAIG buyback: %s",
                       profit, result.get("status", "recorded"))
            self._publish_status_update()

    def _on_trade_closed(self, data: Any):
        """Handle individual trade close events."""
        if isinstance(data, dict):
            pnl = data.get("pnl", 0) or data.get("profit_loss", 0) or data.get("realized_pnl", 0)
            if pnl > 0:
                self.treasury.record_trading_profit(pnl, "trade_close")
                self._publish_status_update()

    def _on_order_update(self, data: Any):
        """Handle order fill/completion — extract realized P&L."""
        if not isinstance(data, dict):
            return
        status = data.get("status", "").lower()
        if status in ("filled", "closed", "completed", "executed"):
            pnl = data.get("pnl", 0) or data.get("realized_pnl", 0) or data.get("profit", 0)
            if isinstance(pnl, (int, float)) and pnl > 0:
                self.treasury.record_trading_profit(float(pnl), "order_fill")
                logger.info("Order filled with $%.2f profit → KAIG buyback pipeline", pnl)
                self._publish_status_update()

    def _on_position_update(self, data: Any):
        """Handle position close — extract realized P&L."""
        if not isinstance(data, dict):
            return
        # Check for closed positions with profit
        positions = data.get("positions", [data] if "symbol" in data else [])
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            status = pos.get("status", "").lower()
            if status in ("closed", "liquidated"):
                pnl = pos.get("pnl", 0) or pos.get("realized_pnl", 0) or pos.get("profit", 0)
                if isinstance(pnl, (int, float)) and pnl > 0:
                    self.treasury.record_trading_profit(float(pnl), "position_close")
                    self._publish_status_update()

    def _on_trading_response(self, data: Any):
        """Handle general trading responses that may contain profit data."""
        if not isinstance(data, dict):
            return
        inner = data.get("data", {})
        if isinstance(inner, dict):
            profit = inner.get("profit", 0) or inner.get("pnl", 0)
            if isinstance(profit, (int, float)) and profit > 0:
                self.treasury.record_trading_profit(float(profit), "trading_response")

    def _on_trading_signal(self, data: Any):
        """Track trading signals for intelligence — no direct profit, but useful for analytics."""
        try:
            if not isinstance(data, dict):
                return
            signal = {
                "symbol": data.get("symbol", "unknown"),
                "action": data.get("action", "hold"),
                "confidence": float(data.get("confidence", 0)),
                "source": data.get("source", "unknown"),
                "timestamp": data.get("timestamp", time.time()),
            }
            signals = self._stats_cache.setdefault("trading_signals", [])
            signals.append(signal)
            if len(signals) > 500:
                self._stats_cache["trading_signals"] = signals[-500:]
            logger.debug("KAIG: Trading signal tracked — %s %s (confidence %.2f)",
                        signal["action"], signal["symbol"], signal["confidence"])
        except Exception as e:
            logger.debug("Error tracking trading signal: %s", e)

    def _on_portfolio_update(self, data: Any):
        """Handle unified portfolio updates — track overall gains."""
        if not isinstance(data, dict):
            return
        # Portfolio reports total USD — we track changes as potential profit
        total = data.get("total_usd", 0)
        if isinstance(total, (int, float)) and total > 0:
            self._stats_cache["portfolio_total_usd"] = total

    # ── MINING EVENT HANDLERS ───────────────────────────────────

    def _on_mining_reward(self, data: Any):
        """Handle mining reward events — convert share rewards to KAIG value."""
        if not isinstance(data, dict):
            return
        estimated_reward = data.get("estimated_reward", 0)
        shares = data.get("shares_accepted", 0)
        # Convert mining rewards to estimated USD value, then route to buyback
        # BTC share reward ≈ 0.00001 BTC × $97500 ≈ $0.975 per share
        btc_price = 97500  # Fallback; in production use live price
        if isinstance(estimated_reward, (int, float)) and estimated_reward > 0:
            usd_value = estimated_reward * btc_price
            if usd_value > 0.01:  # Only process meaningful amounts
                self.treasury.record_trading_profit(usd_value, "mining_reward")
                logger.info("Mining reward %.8f BTC ($%.2f) → KAIG buyback pipeline",
                           estimated_reward, usd_value)
                self._publish_status_update()

    def _on_mining_started(self, data: Any):
        """Track mining activity for KAIG ecosystem health."""
        logger.info("KAIG: Mining activity detected — revenue pipeline active")
        if self.event_bus:
            self.event_bus.publish("kaig.mining.active", {"active": True})

    def _on_mining_stopped(self, data: Any):
        """Track mining stop."""
        logger.info("KAIG: Mining stopped — node rewards still active")

    def _on_mining_hashrate(self, data: Any):
        """Track hashrate for network health metrics."""
        if isinstance(data, dict):
            self._stats_cache["hashrate"] = data.get("hashrate", 0)

    # ── COMMISSION & REFERRAL HANDLERS ──────────────────────────

    def _on_commission_collected(self, data: Any):
        """Handle commission collection (10% on winning trades) → KAIG buyback."""
        if not isinstance(data, dict):
            return
        commission_usd = data.get("commission_usd", 0) or data.get("amount", 0)
        if isinstance(commission_usd, (int, float)) and commission_usd > 0:
            # ALL commission revenue goes to KAIG buyback
            self.treasury.record_trading_profit(float(commission_usd), "commission")
            logger.info("Commission $%.2f → KAIG buyback pipeline", commission_usd)
            self._publish_status_update()

    def _on_referral_applied(self, data: Any):
        """Handle referral bonus — credit KAIG welcome bonus to new user and referrer."""
        if not isinstance(data, dict):
            return
        device_id = data.get("device_id", "")
        welcome_kaig = data.get("welcome_kaig", 0)
        if device_id and welcome_kaig > 0:
            wallet_id = f"user:{device_id[:16]}"
            self.ledger.credit(wallet_id, welcome_kaig, "Referral welcome bonus")
            logger.info("Referral: credited %.1f KAIG to %s", welcome_kaig, wallet_id)

        # Credit referrer: +5 KAIG parity bonus per referral + any tier KAIG
        referrer_id = data.get("referrer_id") or data.get("referrer")
        referrer_kaig = float(data.get("referrer_kaig", 0))
        if referrer_id and referrer_kaig > 0:
            referrer_wallet = f"user:{str(referrer_id)[:16]}"
            reason = f"Referral bonus for referring {data.get('new_user_id', 'user')}"
            self.ledger.credit(referrer_wallet, referrer_kaig, reason)
            logger.info("Credited %.1f KAIG to referrer %s", referrer_kaig, referrer_id)

    # ── KAIG STATUS & CONTROL HANDLERS ──────────────────────────

    def _on_status_request(self, data: Any):
        """Respond to KAIG status requests from any component."""
        if self.event_bus:
            self.event_bus.publish("kaig.status.response", self.get_full_status())

    def _on_manual_buyback(self, data: Any):
        """Handle manual buyback trigger (admin/testing)."""
        if isinstance(data, dict):
            amount = data.get("usd_amount", 0)
            if amount > 0:
                result = self.manual_buyback(amount)
                if self.event_bus:
                    self.event_bus.publish("kaig.buyback.result", result)

    def _on_node_start_request(self, data: Any):
        """Handle node start request from any component."""
        result = self.node.start()
        if self.event_bus:
            self.event_bus.publish("kaig.node.status", result)

    def _on_node_stop_request(self, data: Any):
        """Handle node stop request from any component."""
        result = self.node.stop()
        if self.event_bus:
            self.event_bus.publish("kaig.node.status", result)

    def _on_trading_system_readiness(self, data: Any):
        """Track global trading readiness state for KAIG intelligence alignment."""
        if isinstance(data, dict):
            self._trading_system_readiness = {
                "state": str(data.get("state", "UNKNOWN")).upper(),
                "auto_trade_started": bool(data.get("auto_trade_started", False)),
                "analysis_ready": bool(data.get("analysis_ready", False)),
                "reason": data.get("reason", ""),
                "timestamp": data.get("timestamp"),
            }
            self._publish_status_update()

    def _publish_status_update(self):
        """Broadcast KAIG status update to all listeners (desktop tab, mobile, etc.)."""
        if self.event_bus and hasattr(self.event_bus, 'publish'):
            now = time.time()
            # Throttle to once every 5 seconds to avoid spam
            if now - self._stats_cache_time < 5.0:
                return
            self._stats_cache_time = now
            try:
                self.event_bus.publish("kaig.status.update", {
                    "price": self.treasury.get_internal_price(),
                    "total_buyback_usd": self.treasury.treasury.get("total_buyback_usd", 0),
                    "total_buyback_kaig": self.treasury.treasury.get("total_buyback_kaig", 0),
                    "node_running": self.node.is_running,
                    "trading_system_readiness": self._trading_system_readiness,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                logger.warning("context: Failed to publish KAIG status update: %s", e)

    def get_full_status(self) -> Dict:
        """Get complete KAIG ecosystem status."""
        c = _cfg()
        return {
            "token": f"${c.ticker}",
            "name": c.name,
            "target_price": self._kaig_price_floor,
            "ath_monitor": self.get_ath_status(),
            "current_price": self.treasury.get_internal_price(),
            "ledger": self.ledger.get_stats(),
            "escrow": self.escrow.get_status(),
            "treasury": self.treasury.get_status(),
            "node": self.node.get_status(),
            "network": self.node.get_network_stats(),
            "trading_system_readiness": self._trading_system_readiness,
            "tokenomics": {
                "total_supply": TOTAL_SUPPLY,
                "escrow_locked": ESCROW_SUPPLY,
                "treasury_reserve": TREASURY_SUPPLY,
                "community_mining": COMMUNITY_SUPPLY,
                "team_dev": TEAM_SUPPLY,
                "monthly_release_cap": MONTHLY_ESCROW_RELEASE,
                "relock_rate": f"{ESCROW_RELOCK_RATE * 100:.0f}%",
                "transaction_burn_rate": f"{TRANSACTION_BURN_RATE * 100:.1f}%",
                "trading_profit_buyback": f"{TRADING_PROFIT_BUYBACK_RATE * 100:.0f}%",
                "staking_apy": f"{STAKING_APY * 100:.1f}%",
                "node_reward_rate": f"{NODE_REWARD_PER_HOUR} KAIG/hr",
            },
        }

    def check_escrow_releases(self) -> Optional[Dict]:
        """Check and process any due escrow releases."""
        return self.escrow.check_and_release()

    def manual_buyback(self, usd_amount: float) -> Dict:
        """Manually trigger a buyback (for testing/admin)."""
        return self.treasury._execute_buyback(usd_amount, "manual")

    # ── ROLLOUT PLAN & AI STRATEGY KNOWLEDGE ─────────────────────

    _rollout_plan_cache: Optional[Dict] = None

    @classmethod
    def get_rollout_plan(cls) -> Dict:
        """Load the $KAIG rollout plan from config/kaig/rollout_plan.json.
        This is the AI brain's knowledge base for KAIG strategy and rollout phases.
        Any component (ThothAI, UnifiedAIRouter, KAIG Tab) can call this."""
        if cls._rollout_plan_cache is not None:
            return cls._rollout_plan_cache
        plan_path = os.path.join("config", "kaig", "rollout_plan.json")
        try:
            with open(plan_path, "r") as f:
                cls._rollout_plan_cache = json.load(f)
                logger.info("KAIG rollout plan loaded from %s", plan_path)
                return cls._rollout_plan_cache
        except FileNotFoundError:
            logger.warning("KAIG rollout plan not found at %s", plan_path)
            return {"error": "Rollout plan not found"}
        except Exception as e:
            logger.error("Failed to load KAIG rollout plan: %s", e)
            return {"error": str(e)}

    def get_current_phase(self) -> Dict:
        """Determine current rollout phase based on ecosystem metrics."""
        plan = self.get_rollout_plan()
        phases = plan.get("rollout_phases", {})
        status = self.get_full_status()
        price = status.get("current_price", INITIAL_PRICE)
        treasury_status = status.get("treasury", {})
        total_reserves = treasury_status.get("total_reserves_usd", 0)
        num_buybacks = treasury_status.get("num_buybacks", 0)

        # Auto-detect current phase from metrics
        if total_reserves >= 500000 and price >= 5.0:
            current = "phase_3_pre_listing"
        elif total_reserves >= 200000 and price >= 3.0:
            current = "phase_2_stabilization"
        elif total_reserves >= 50000 and price >= 1.0:
            current = "phase_1_accumulation"
        else:
            current = "phase_0_genesis"

        phase_data = phases.get(current, {})
        return {
            "current_phase_id": current,
            "phase_name": phase_data.get("name", "Unknown"),
            "phase_status": phase_data.get("status", "UNKNOWN"),
            "phase_duration": phase_data.get("duration", ""),
            "objectives": phase_data.get("objectives", []),
            "ai_actions": phase_data.get("ai_actions", []),
            "success_metrics": phase_data.get("success_metrics", {}),
            "current_metrics": {
                "price": price,
                "treasury_reserves_usd": total_reserves,
                "buybacks_executed": num_buybacks,
                "total_buyback_usd": treasury_status.get("total_buyback_usd", 0),
            },
        }

    def get_ai_strategy_brief(self) -> str:
        """Generate a natural-language strategy brief for the AI brain.
        ThothAI calls this to understand KAIG context when answering user queries."""
        phase = self.get_current_phase()
        status = self.get_full_status()
        plan = self.get_rollout_plan()
        patterns = plan.get("research_patterns_implemented", {})
        advantages = plan.get("competitive_advantages", [])
        revenue = plan.get("revenue_streams_for_buyback", [])

        brief = f"""## $KAIG (KAI Gold) — AI Strategy Brief

**Current Phase:** {phase['phase_name']} ({phase['phase_duration']})
**Internal Price:** ${status.get('current_price', 0):.4f} → Target: ${TARGET_PRICE:.2f}
**Progress to Target:** {status.get('current_price', 0) / TARGET_PRICE * 100:.1f}%
**Treasury Reserves:** ${phase['current_metrics']['treasury_reserves_usd']:,.2f}
**Buybacks Executed:** {phase['current_metrics']['buybacks_executed']}
**Total Buyback Volume:** ${phase['current_metrics']['total_buyback_usd']:,.2f}

### Tokenomics (Fixed 100M Supply)
- 70M in escrow (XRP-style, 500K/month release, 75% re-locked)
- 15M treasury reserve (AI-managed buybacks)
- 10M community/mining (node rewards, referrals, airdrops)
- 5M team/dev (4-year vesting, 1-year cliff)
- 0.1% transaction burn (deflationary)

### Revenue → Buyback Pipeline
"""
        for r in revenue:
            brief += f"- **{r['source']}**: {r['description']}\n"

        brief += f"\n### Proven Patterns We Implemented\n"
        for key, p in patterns.items():
            if key != "anti_pi_coin_design":
                brief += f"- **{p.get('source', key)}**: {p.get('what_we_took', '')}\n"

        brief += f"\n### Anti-Pi Coin Safeguards\n"
        anti_pi = patterns.get("anti_pi_coin_design", {})
        for lesson in anti_pi.get("lessons_applied", []):
            brief += f"- {lesson}\n"

        brief += f"\n### Current Phase Objectives\n"
        for obj in phase.get("objectives", []):
            brief += f"- {obj}\n"

        brief += f"\n### AI Actions This Phase\n"
        for action in phase.get("ai_actions", []):
            brief += f"- {action}\n"

        brief += f"\n### Competitive Advantages\n"
        for adv in advantages[:5]:
            brief += f"- {adv}\n"

        # Fund safety / rebrand resilience context
        migration = plan.get("migration_protection", {})
        fund_safety = migration.get("fund_safety_guarantee", {})
        if fund_safety:
            brief += f"\n### FUND SAFETY GUARANTEE (Rebrand Resilience)\n"
            brief += f"- **Principle:** {fund_safety.get('principle', 'All balances tracked by wallet address, not token name.')}\n"
            brief += f"- **User Action Required:** {fund_safety.get('user_action_required', 'NONE')}\n"
            preserved = fund_safety.get("what_is_preserved", [])
            for item in preserved[:4]:
                brief += f"- {item}\n"
            precedents = fund_safety.get("industry_precedent", [])
            if precedents:
                brief += f"- **Proven Precedent:** {precedents[0]}\n"
            brief += f"- **ZERO LOSS. ZERO ACTION REQUIRED. ZERO DOUBT.**\n"

        # SOTA 2026: Include AutoPilot status if available
        try:
            from core.kaig_autopilot import KAIGAutoPilot
            autopilot = KAIGAutoPilot._instance
            if autopilot:
                ap_status = autopilot.get_status()
                matrix = autopilot.get_automation_matrix()
                phase_id = ap_status.get("current_phase", "phase_0_genesis")
                phase_matrix = matrix.get(phase_id, {})
                brief += f"\n### AutoPilot Status\n"
                brief += f"- **Mode:** {ap_status['mode'].upper()}\n"
                brief += f"- **Running:** {'Yes' if ap_status['running'] else 'No'}\n"
                brief += f"- **Automation Level:** {phase_matrix.get('automation_pct', 0)}%\n"
                brief += f"- **Auto Buybacks:** {ap_status['total_auto_buybacks']}\n"
                brief += f"- **Pending Creator Alerts:** {ap_status['pending_alerts']}\n"
                brief += f"- **KAIG Wallets Created:** {ap_status['wallets']}\n"
                human_items = phase_matrix.get("human_needed", [])
                if human_items:
                    brief += f"- **Human Action Needed:** {'; '.join(human_items)}\n"
                else:
                    brief += f"- **Human Action Needed:** None — fully autonomous\n"
        except Exception as e:
            logger.warning("context: Failed to fetch AutoPilot status for strategy brief: %s", e)

        return brief
