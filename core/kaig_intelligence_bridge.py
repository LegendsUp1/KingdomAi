"""
KAIG Intelligence Bridge — Wires KAIG Goals Into Every Intelligence System
===========================================================================

This is the CRITICAL missing piece: the bridge that makes Trading Intelligence,
Mining Intelligence, and Wallet Intelligence AWARE of KAIG's goals and act on them.

Architecture:
  ┌──────────────────────┐
  │  KAIG Runtime Config  │  ← Hot-reloadable JSON
  └──────────┬───────────┘
             │
  ┌──────────▼───────────┐
  │  KAIGIntelBridge     │  ← THIS FILE — singleton orchestrator
  │  (event bus wired)   │
  └──┬────────┬────────┬─┘
     │        │        │
  ┌──▼──┐ ┌──▼──┐ ┌──▼──┐
  │Trade│ │Mine │ │Wall │   ← Intelligence systems receive KAIG directives
  │Intel│ │Intel│ │Intel│     via event bus topics
  └─────┘ └─────┘ └─────┘

Event Topics Published:
  kaig.intel.trading.directive   → Trading Intelligence receives profit goals & speed mandate
  kaig.intel.mining.directive    → Mining Intelligence receives reward routing & algorithm priorities
  kaig.intel.wallet.directive    → Wallet Intelligence receives treasury monitoring orders
  kaig.intel.speed.mandate       → ALL systems receive speed priority update
  kaig.intel.status              → Bridge status broadcast

Event Topics Subscribed:
  trading.trade_completed        → Track profit for KAIG buyback pipeline
  trading.profit_report          → Aggregate profit data
  mining.reward_update           → Track mining rewards for treasury
  mining.intelligence.update     → Mining optimization cycle data
  wallet.balance_update          → Treasury reserve monitoring
  kaig.status.update             → KAIG engine status
  kaig.intel.request             → On-demand directive refresh
"""

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("KingdomAI.KAIG.IntelBridge")

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


class KAIGIntelligenceBridge:
    """Bridges KAIG strategy goals into the Trading, Mining, and Wallet intelligence systems.

    This singleton continuously pushes KAIG-aware directives to all intelligence
    components via the event bus, ensuring every subsystem knows:
      1. WHY it's trading/mining/tracking (to fund KAIG treasury & buybacks)
      2. HOW FAST it should operate (speed mandate from runtime config)
      3. WHAT metrics matter (profit targets, reward routing, reserve thresholds)
    """

    _instance: Optional["KAIGIntelligenceBridge"] = None
    _lock = threading.Lock()

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

        # Tracked metrics from intelligence systems
        self._trading_profit_today_usd = 0.0
        self._trading_profit_total_usd = 0.0
        self._mining_rewards_today_usd = 0.0
        self._treasury_reserves_usd = 0.0
        self._kaig_price = 0.10
        self._total_buybacks = 0
        self._last_directive_time = 0.0
        self._cycle_count = 0

        # ATH price floor — 1 KAIG must always exceed the highest crypto ATH ever
        self._ath_record_coin = "BTC"
        self._ath_record_price = 125835.92
        self._kaig_price_floor = 125835.93

        # Load config
        self._cfg = None
        self._load_config()

        logger.info("KAIGIntelligenceBridge initialized — ready to wire KAIG goals into all intelligence systems")

    # ── SINGLETON ────────────────────────────────────────────────

    @classmethod
    def get_instance(cls, event_bus=None) -> "KAIGIntelligenceBridge":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(event_bus=event_bus)
        if event_bus and cls._instance.event_bus is None:
            cls._instance.event_bus = event_bus
        return cls._instance

    # ── LIFECYCLE ────────────────────────────────────────────────

    def start(self, event_bus=None):
        """Start the intelligence bridge — subscribe to events and begin directive loop."""
        if event_bus:
            self.event_bus = event_bus
        if not self.event_bus:
            logger.error("Cannot start KAIGIntelBridge — no event bus")
            return False

        self._subscribe_events()
        self._running = True

        # Push initial directives immediately
        self._push_all_directives()

        # Start async loop if event loop is available
        try:
            loop = asyncio.get_running_loop()
            self._loop_task = loop.create_task(self._directive_loop())
        except RuntimeError:
            # No event loop — use thread
            t = threading.Thread(target=self._directive_loop_sync, daemon=True,
                                name="KAIG-IntelBridge")
            t.start()

        logger.info("KAIGIntelligenceBridge STARTED — directives flowing to all intelligence systems")
        return True

    def stop(self):
        """Stop the bridge."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
        logger.info("KAIGIntelligenceBridge stopped")

    # ── EVENT SUBSCRIPTIONS ──────────────────────────────────────

    def _subscribe_events(self):
        """Subscribe to events from all intelligence systems."""
        eb = self.event_bus
        if not eb:
            return

        # Register event bus with token identity module so rebrand events propagate
        try:
            from core.kaig_token_identity import set_event_bus
            set_event_bus(eb)
        except Exception as e:
            logger.debug("Could not register event bus with token identity: %s", e)

        sub = getattr(eb, 'subscribe_sync', None) or eb.subscribe

        # Trading events → track profits for KAIG
        sub('trading.trade_completed', self._on_trade_completed)
        sub('trading.profit_report', self._on_profit_report)
        sub('trading.opportunities.high_value', self._on_high_value_opportunity)

        # Mining events → track rewards for KAIG
        sub('mining.reward_update', self._on_mining_reward)
        sub('mining.intelligence.update', self._on_mining_intel_update)

        # Wallet events → track treasury reserves
        sub('wallet.balance_update', self._on_wallet_balance_update)

        # Token identity change → reload config and push new directives
        sub('kaig.identity.changed', self._on_identity_changed)

        # KAIG engine events
        sub('kaig.status.update', self._on_kaig_status_update)
        sub('kaig.buyback.result', self._on_buyback_result)
        sub('kaig.ath.update', self._on_ath_update)

        # On-demand directive refresh
        sub('kaig.intel.request', self._on_directive_request)

        # Config change → re-push directives
        sub('kaig.config.changed', self._on_config_changed)

        logger.info("KAIGIntelBridge subscribed to trading/mining/wallet/kaig events")

    # ── DIRECTIVE PUBLISHING ─────────────────────────────────────

    def _ai_strategic_analysis(self) -> Dict:
        """Consult the Ollama brain for a strategic KAIG ecosystem recommendation.

        Runs every 30 cycles (~5min at 10s interval) to avoid overloading the model.
        Returns strategic guidance that all intelligence systems can act on.
        """
        if not _ensure_orch():
            return {}
        try:
            import requests
            model = _orch.get_model_for_task("kaig")
            url = get_ollama_url()
            prompt = (
                f"You are the strategic brain for the $KAIG cryptocurrency ecosystem.\n"
                f"Current state:\n"
                f"- Trading profit today: ${self._trading_profit_today_usd:.2f}\n"
                f"- Total trading profit: ${self._trading_profit_total_usd:.2f}\n"
                f"- Mining rewards today: ${self._mining_rewards_today_usd:.2f}\n"
                f"- Treasury reserves: ${self._treasury_reserves_usd:.2f}\n"
                f"- KAIG price: ${self._kaig_price:.4f}\n"
                f"- Total buybacks executed: {self._total_buybacks}\n"
                f"- Price floor (must exceed highest ATH): ${self._kaig_price_floor:,.2f}\n"
                f"- Survival target: $26,000 realized gains\n\n"
                f"Respond with ONLY valid JSON:\n"
                f'{{"trading_priority": "aggressive/moderate/conservative", '
                f'"mining_priority": "aggressive/moderate/conservative", '
                f'"buyback_recommendation": "execute_now/accumulate/defer", '
                f'"risk_level": "low/medium/high", '
                f'"one_line_strategy": "one sentence max"}}'
            )
            resp = requests.post(
                f"{url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": 150, "temperature": 0.3},
                      "keep_alive": -1},
                timeout=30,
            )
            if resp.status_code == 200:
                raw = resp.json().get("response", "")
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    import json as _json
                    parsed = _json.loads(raw[start:end])
                    logger.info("KAIG AI strategic analysis: %s | %s",
                                parsed.get("one_line_strategy", ""),
                                parsed.get("buyback_recommendation", ""))
                    return parsed
        except Exception as e:
            logger.debug("KAIG AI strategic analysis unavailable: %s", e)
        return {}

    def _push_all_directives(self):
        """Push KAIG-aware directives to ALL intelligence systems at once."""
        self._load_config()  # Refresh config
        now = time.time()
        self._last_directive_time = now
        self._cycle_count += 1

        cfg = self._cfg or {}
        goals = cfg.get("intelligence_goals", {})
        speed = cfg.get("speed_policy", {})
        token = cfg.get("token", {})
        tokenomics = cfg.get("tokenomics", {})
        deployment = cfg.get("deployment", {})

        # ── AI STRATEGIC ANALYSIS (every 30 cycles ≈ 5min) ────────
        ai_strategy = {}
        if self._cycle_count % 30 == 1:
            ai_strategy = self._ai_strategic_analysis()
        if not hasattr(self, "_last_ai_strategy"):
            self._last_ai_strategy = {}
        if ai_strategy:
            self._last_ai_strategy = ai_strategy
        else:
            ai_strategy = getattr(self, "_last_ai_strategy", {})

        # ── TRADING DIRECTIVE ────────────────────────────────────
        trading_goals = goals.get("trading", {})
        survival = cfg.get("kaig_survival_target", {})
        trading_directive = {
            "source": "kaig_intelligence_bridge",
            "timestamp": datetime.utcnow().isoformat(),
            "cycle": self._cycle_count,
            "token_ticker": token.get("ticker", "KAIG"),
            "token_name": token.get("name", "KAI Gold"),

            # TWO DISTINCT TARGETS — the system MUST know the difference
            # 1. SURVIVAL FLOOR: $26K realized gains → $13K to KAIG treasury (50% buyback)
            #    If this is not met, KAIG cannot launch. This is existential.
            # 2. ULTIMATE TARGET: $2T long-term profit target (already in TradingHub)
            #    This is the aspirational ceiling. Always pursue, but survival comes first.
            "kaig_survival_floor": {
                "required_realized_gains_usd": survival.get("required_realized_gains_usd", 26000),
                "kaig_treasury_target_usd": survival.get("launch_cost_usd", 13000),
                "buyback_rate": survival.get("buyback_rate", 0.50),
                "funding_source": survival.get("funding_source", "creator_only"),
                "consumer_users": survival.get("consumer_users", 0),
                "urgency": survival.get("urgency", "existential"),
                "survival_met": self._trading_profit_total_usd >= survival.get("required_realized_gains_usd", 26000),
            },
            "ultimate_profit_target_usd": 2_000_000_000_000,

            # 3. KAIG PRICE FLOOR: 1 KAIG > highest crypto ATH ever (live-monitored)
            "kaig_price_floor": {
                "goal": "1 KAIG must always be priced higher than the highest crypto ATH ever recorded",
                "current_ath_coin": self._ath_record_coin,
                "current_ath_price_usd": self._ath_record_price,
                "kaig_must_exceed_usd": self._kaig_price_floor,
                "live_monitored": True,
            },

            # THE MISSION
            "primary_goal": trading_goals.get("primary_goal",
                "Generate $26,000 in realized gains (survival floor) then pursue $2T ultimate target"),
            "profit_routing": trading_goals.get("profit_routing",
                "50% of ALL realized trading profits auto-route to KAIG treasury buyback"),

            # TARGETS
            "buyback_rate": cfg.get("buyback", {}).get("trading_profit_rate", 0.50),
            "risk_tolerance": trading_goals.get("risk_tolerance", "moderate_aggressive"),
            "priority_pairs": trading_goals.get("priority_pairs", []),
            "no_consumer_users": trading_goals.get("no_consumer_users", True),

            # CURRENT STATUS
            "profit_today_usd": self._trading_profit_today_usd,
            "profit_total_usd": self._trading_profit_total_usd,
            "kaig_price": self._kaig_price,
            "target_price": tokenomics.get("target_price", 10.0),
            "treasury_reserves_usd": self._treasury_reserves_usd,
            "total_buybacks": self._total_buybacks,

            # DEPLOYMENT STATE
            "deployment_mode": deployment.get("mode", "pre_launch"),
            "on_chain": deployment.get("on_chain_deployed", False),

            # AI STRATEGIC GUIDANCE (from Ollama brain)
            "ai_strategy": {
                "trading_priority": ai_strategy.get("trading_priority", "aggressive"),
                "buyback_recommendation": ai_strategy.get("buyback_recommendation", "execute_now"),
                "risk_level": ai_strategy.get("risk_level", "medium"),
                "strategy_summary": ai_strategy.get("one_line_strategy", ""),
            },
        }

        if self.event_bus:
            self.event_bus.publish("kaig.intel.trading.directive", trading_directive)

        # ── MINING DIRECTIVE ─────────────────────────────────────
        mining_goals = goals.get("mining", {})
        mining_directive = {
            "source": "kaig_intelligence_bridge",
            "timestamp": datetime.utcnow().isoformat(),
            "cycle": self._cycle_count,
            "token_ticker": token.get("ticker", "KAIG"),

            # THE MISSION
            "primary_goal": mining_goals.get("primary_goal",
                "Mine most profitable coins and convert rewards to KAIG treasury backing"),
            "speed_mandate": mining_goals.get("speed_mandate",
                "Optimize hashrate allocation in real-time"),
            "reward_routing": mining_goals.get("reward_routing",
                "All mining rewards valued in USD and routed to KAIG buyback pipeline"),

            # TARGETS
            "aggressive_mode": mining_goals.get("aggressive_mode", True),
            "target_coins_mined": mining_goals.get("target_coins_mined", 1000),
            "auto_switch_algorithm": mining_goals.get("auto_switch_algorithm", True),
            "priority_algorithms": mining_goals.get("priority_algorithms",
                ["sha256", "ethash", "randomx", "kaspa"]),

            # CURRENT STATUS
            "mining_rewards_today_usd": self._mining_rewards_today_usd,
            "kaig_price": self._kaig_price,
            "treasury_reserves_usd": self._treasury_reserves_usd,

            # SPEED CONFIG
            "optimization_interval_seconds": speed.get("mining_optimization_interval_seconds", 60),

            # NODE REWARDS
            "node_reward_per_hour": cfg.get("node_rewards", {}).get("reward_per_hour", 0.5),
            "node_reward_cap_daily": cfg.get("node_rewards", {}).get("reward_cap_daily", 12.0),

            # AI STRATEGIC GUIDANCE
            "ai_strategy": {
                "mining_priority": ai_strategy.get("mining_priority", "aggressive"),
                "strategy_summary": ai_strategy.get("one_line_strategy", ""),
            },
        }

        if self.event_bus:
            self.event_bus.publish("kaig.intel.mining.directive", mining_directive)

        # ── WALLET DIRECTIVE ─────────────────────────────────────
        wallet_goals = goals.get("wallet", {})
        wallet_directive = {
            "source": "kaig_intelligence_bridge",
            "timestamp": datetime.utcnow().isoformat(),
            "cycle": self._cycle_count,
            "token_ticker": token.get("ticker", "KAIG"),

            # THE MISSION
            "primary_goal": wallet_goals.get("primary_goal",
                "Track all KAIG wallets, treasury reserves, and liquidity positions"),
            "speed_mandate": wallet_goals.get("speed_mandate",
                "Balance updates must be near real-time"),

            # MONITORING ORDERS
            "monitor_treasury_reserves": wallet_goals.get("monitor_treasury_reserves", True),
            "monitor_escrow_releases": wallet_goals.get("monitor_escrow_releases", True),
            "monitor_burn_rate": wallet_goals.get("monitor_burn_rate", True),
            "alert_on_low_reserves_usd": wallet_goals.get("alert_on_low_reserves_usd", 1000.0),

            # CURRENT STATUS
            "treasury_reserves_usd": self._treasury_reserves_usd,
            "kaig_price": self._kaig_price,
            "total_buybacks": self._total_buybacks,

            # CONTRACT ADDRESSES (for on-chain monitoring when deployed)
            "contract_addresses": deployment.get("contract_addresses", {}),
            "on_chain": deployment.get("on_chain_deployed", False),

            # SPEED CONFIG
            "refresh_interval_seconds": speed.get("wallet_refresh_interval_seconds", 15),
        }

        if self.event_bus:
            self.event_bus.publish("kaig.intel.wallet.directive", wallet_directive)

        # ── SPEED MANDATE (broadcast to ALL systems) ─────────────
        speed_mandate = {
            "source": "kaig_intelligence_bridge",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "SPEED IS OF THE ESSENCE — all systems must prioritize fast execution",
            "trading_execution_priority": speed.get("trading_execution_priority", "maximum"),
            "mining_optimization_interval": speed.get("mining_optimization_interval_seconds", 60),
            "buyback_check_interval": speed.get("buyback_check_interval_seconds", 30),
            "wallet_refresh_interval": speed.get("wallet_refresh_interval_seconds", 15),
            "intelligence_cycle": speed.get("intelligence_cycle_seconds", 10),
        }

        if self.event_bus:
            self.event_bus.publish("kaig.intel.speed.mandate", speed_mandate)

        # ── BRIDGE STATUS ────────────────────────────────────────
        if self.event_bus:
            self.event_bus.publish("kaig.intel.status", {
                "bridge_active": True,
                "cycle": self._cycle_count,
                "trading_profit_today": self._trading_profit_today_usd,
                "mining_rewards_today": self._mining_rewards_today_usd,
                "treasury_reserves": self._treasury_reserves_usd,
                "kaig_price": self._kaig_price,
                "total_buybacks": self._total_buybacks,
                "timestamp": datetime.utcnow().isoformat(),
            })

        if self._cycle_count <= 1 or self._cycle_count % 10 == 0:
            logger.info("KAIG directives pushed: cycle=%d, profit_today=$%.2f, "
                       "mining_today=$%.2f, treasury=$%.2f, price=$%.4f",
                       self._cycle_count, self._trading_profit_today_usd,
                       self._mining_rewards_today_usd, self._treasury_reserves_usd,
                       self._kaig_price)

    # ── EVENT HANDLERS ───────────────────────────────────────────

    def _on_trade_completed(self, data: Dict):
        """Track completed trades for KAIG profit metrics."""
        if not isinstance(data, dict):
            return
        trade = data.get("trade", data)
        pnl = trade.get("profit_loss") or trade.get("pnl") or trade.get("profit") or 0
        try:
            pnl = float(pnl)
        except (TypeError, ValueError):
            return
        if pnl > 0:
            self._trading_profit_today_usd += pnl
            self._trading_profit_total_usd += pnl
            # Check survival floor progress
            survival_target = 26000
            if self._cfg:
                survival_target = self._cfg.get("kaig_survival_target", {}).get(
                    "required_realized_gains_usd", 26000)
            progress_pct = (self._trading_profit_total_usd / survival_target) * 100
            logger.info("KAIG IntelBridge: trade profit +$%.2f | TOTAL: $%.2f / $%.0f (%.1f%%) | "
                       "KAIG treasury needs: $%.0f more in realized gains",
                       pnl, self._trading_profit_total_usd, survival_target, progress_pct,
                       max(0, survival_target - self._trading_profit_total_usd))

    def _on_profit_report(self, data: Dict):
        """Handle aggregated profit reports."""
        if isinstance(data, dict):
            total = data.get("total_profit_usd") or data.get("profit_usd") or 0
            cumulative = data.get("current_profit") or data.get("cumulative_profit_usd") or 0
            try:
                self._trading_profit_today_usd = max(self._trading_profit_today_usd, float(total))
                if float(cumulative) > self._trading_profit_total_usd:
                    self._trading_profit_total_usd = float(cumulative)
            except (TypeError, ValueError):
                pass

    def _on_high_value_opportunity(self, data: Dict):
        """Log high-value trading opportunities for KAIG awareness."""
        if isinstance(data, dict):
            count = data.get("count", 0)
            if count > 0:
                logger.info("KAIG IntelBridge: %d high-value trading opportunities detected — "
                          "EXECUTE FAST for KAIG buyback revenue", count)

    def _on_mining_reward(self, data: Dict):
        """Track mining rewards for KAIG treasury."""
        if not isinstance(data, dict):
            return
        reward_usd = data.get("estimated_reward_usd") or 0
        if not reward_usd:
            reward = data.get("estimated_reward") or data.get("reward") or 0
            try:
                reward_usd = float(reward) * 97500  # Fallback BTC price
            except (TypeError, ValueError):
                return
        try:
            self._mining_rewards_today_usd += float(reward_usd)
        except (TypeError, ValueError):
            pass

    def _on_mining_intel_update(self, data: Dict):
        """Track mining intelligence cycle status."""
        try:
            if not isinstance(data, dict):
                return
            cycle_id = data.get("cycle_id", "unknown")
            hashrate = data.get("hashrate", 0)
            algorithm = data.get("algorithm", "unknown")
            efficiency = data.get("efficiency", 0)
            estimated_daily_usd = data.get("estimated_daily_usd", 0)

            if hashrate:
                try:
                    self._mining_rewards_today_usd = max(
                        self._mining_rewards_today_usd,
                        float(estimated_daily_usd)
                    )
                except (TypeError, ValueError):
                    pass

            logger.debug(
                "KAIG IntelBridge: Mining intel cycle %s — algo=%s, hashrate=%s, efficiency=%.2f",
                cycle_id, algorithm, hashrate, efficiency
            )
        except Exception as e:
            logger.debug("Error processing mining intel update: %s", e)

    def _on_wallet_balance_update(self, data: Dict):
        """Track wallet balance changes for treasury monitoring."""
        if isinstance(data, dict):
            # Look for treasury-specific balance
            if data.get("wallet_type") == "treasury" or data.get("network") == "KAIG":
                balance = data.get("balance_usd") or data.get("balance") or 0
                try:
                    self._treasury_reserves_usd = float(balance)
                except (TypeError, ValueError):
                    pass

    def _on_kaig_status_update(self, data: Dict):
        """Track KAIG engine status updates."""
        if isinstance(data, dict):
            price = data.get("price")
            if price:
                try:
                    self._kaig_price = float(price)
                except (TypeError, ValueError):
                    pass
            buyback_usd = data.get("total_buyback_usd")
            if buyback_usd is not None:
                try:
                    self._total_buybacks = int(buyback_usd)
                except (TypeError, ValueError):
                    pass

    def _on_buyback_result(self, data: Dict):
        """Track buyback execution results."""
        if isinstance(data, dict):
            logger.info("KAIG IntelBridge: Buyback executed — %s", data.get("status", "unknown"))

    def _on_ath_update(self, data: Dict):
        """Handle new crypto ATH detection — KAIG price floor must rise."""
        if not isinstance(data, dict):
            return
        new_coin = data.get("new_ath_coin", "")
        new_price = data.get("new_ath_price", 0)
        new_floor = data.get("kaig_price_floor", 0)
        if new_price > self._ath_record_price:
            self._ath_record_coin = new_coin
            self._ath_record_price = new_price
            self._kaig_price_floor = new_floor
            logger.warning(
                "KAIG IntelBridge: NEW ATH — %s hit $%s. "
                "KAIG price floor raised to $%s. Pushing new directives.",
                new_coin, f"{new_price:,.2f}", f"{new_floor:,.2f}")
            # Immediately re-push directives with new floor
            self._push_all_directives()

    def _on_directive_request(self, data: Dict):
        """Handle on-demand directive refresh requests."""
        logger.info("KAIG IntelBridge: On-demand directive refresh requested")
        self._push_all_directives()

    def _on_identity_changed(self, data):
        """Handle token rebrand — reload config and re-push directives with new identity.

        This fires when execute_rebrand() is called from kaig_token_identity.py.
        All directives are immediately re-pushed so every system sees the new ticker/name.
        User funds are NOT affected — only labels change.
        """
        if isinstance(data, dict):
            logger.warning(
                "TOKEN IDENTITY CHANGED: %s → %s | Reloading config and pushing new directives",
                data.get("old_ticker", "?"), data.get("new_ticker", "?"),
            )
        self._load_config()
        self._push_all_directives()

    def _on_config_changed(self, data: Dict):
        """Handle config change notification — re-push directives with new values."""
        logger.info("KAIG IntelBridge: Config changed — re-pushing directives")
        self._push_all_directives()

    # ── DIRECTIVE LOOP ───────────────────────────────────────────

    async def _directive_loop(self):
        """Async loop that pushes directives at configured intervals."""
        logger.info("KAIG IntelBridge directive loop started (async)")
        while self._running:
            try:
                interval = 10  # Default
                if self._cfg:
                    interval = self._cfg.get("speed_policy", {}).get(
                        "intelligence_cycle_seconds", 10)
                await asyncio.sleep(interval)
                self._push_all_directives()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("KAIG IntelBridge loop error: %s", e)
                await asyncio.sleep(5)

    def _directive_loop_sync(self):
        """Sync fallback loop for when no async event loop is available."""
        logger.info("KAIG IntelBridge directive loop started (sync thread)")
        while self._running:
            try:
                interval = 10
                if self._cfg:
                    interval = self._cfg.get("speed_policy", {}).get(
                        "intelligence_cycle_seconds", 10)
                time.sleep(interval)
                self._push_all_directives()
            except Exception as e:
                logger.error("KAIG IntelBridge loop error: %s", e)
                time.sleep(5)

    # ── CONFIG ───────────────────────────────────────────────────

    def _load_config(self):
        """Load runtime config from JSON."""
        try:
            cfg_path = os.path.join("config", "kaig", "runtime_config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    self._cfg = json.load(f)
            else:
                self._cfg = {}
        except Exception as e:
            logger.warning("Failed to load KAIG runtime config: %s", e)
            if self._cfg is None:
                self._cfg = {}

    # ── INTELLIGENCE QUERY API ───────────────────────────────────

    def get_trading_brief(self) -> str:
        """Get a natural-language brief for the trading intelligence system."""
        cfg = self._cfg or {}
        goals = cfg.get("intelligence_goals", {}).get("trading", {})
        survival = cfg.get("kaig_survival_target", {})
        ticker = cfg.get("token", {}).get("ticker", "KAIG")
        survival_target = survival.get("required_realized_gains_usd", 26000)
        treasury_target = survival.get("launch_cost_usd", 13000)
        remaining = max(0, survival_target - self._trading_profit_total_usd)
        survival_met = self._trading_profit_total_usd >= survival_target
        progress_pct = min(100, (self._trading_profit_total_usd / survival_target) * 100) if survival_target else 0
        return (
            f"TRADING INTELLIGENCE DIRECTIVE from ${ticker} Bridge:\n"
            f"\n"
            f"=== THREE TARGETS (know the difference) ===\n"
            f"\n"
            f"1. SURVIVAL FLOOR (existential, FIRST):\n"
            f"   Required realized gains: ${survival_target:,.0f}\n"
            f"   → 50% buyback → ${treasury_target:,.0f} to ${ticker} treasury for launch\n"
            f"   Current total realized: ${self._trading_profit_total_usd:,.2f}\n"
            f"   Remaining needed: ${remaining:,.2f}\n"
            f"   Progress: {progress_pct:.1f}%\n"
            f"   Status: {'MET ✓' if survival_met else 'NOT MET — EXISTENTIAL PRIORITY'}\n"
            f"   Funding: Creator capital only (0 consumer users)\n"
            f"\n"
            f"2. KAIG PRICE FLOOR (always-realizing, live-monitored):\n"
            f"   1 ${ticker} must ALWAYS be priced higher than the highest crypto ATH ever\n"
            f"   Current highest ATH: {self._ath_record_coin} at ${self._ath_record_price:,.2f}\n"
            f"   ${ticker} price floor: ${self._kaig_price_floor:,.2f}\n"
            f"\n"
            f"3. ULTIMATE TARGET (aspirational, always pursue):\n"
            f"   $2,000,000,000,000\n"
            f"\n"
            f"PROFIT ROUTING: {goals.get('profit_routing', '50% of ALL realized profits → KAIG buyback')}\n"
            f"TODAY: ${self._trading_profit_today_usd:.2f} profit generated\n"
            f"ACTION: {'Pursue $2T target — survival floor is met.' if survival_met else 'SURVIVAL FIRST. Generate realized gains. KAIG cannot launch until this floor is met.'}"
        )

    def get_mining_brief(self) -> str:
        """Get a natural-language brief for the mining intelligence system."""
        cfg = self._cfg or {}
        goals = cfg.get("intelligence_goals", {}).get("mining", {})
        ticker = cfg.get("token", {}).get("ticker", "KAIG")
        return (
            f"MINING INTELLIGENCE DIRECTIVE from ${ticker} Bridge:\n"
            f"PRIMARY GOAL: {goals.get('primary_goal', 'Mine most profitable coins')}\n"
            f"SPEED: {goals.get('speed_mandate', 'Real-time optimization')}\n"
            f"REWARD ROUTING: {goals.get('reward_routing', 'All rewards to buyback')}\n"
            f"TODAY: ${self._mining_rewards_today_usd:.2f} in mining rewards\n"
            f"ACTION: Mine aggressively. All rewards fund ${ticker} treasury. "
            f"Switch algorithms instantly for maximum profitability."
        )

    def get_wallet_brief(self) -> str:
        """Get a natural-language brief for the wallet intelligence system."""
        cfg = self._cfg or {}
        goals = cfg.get("intelligence_goals", {}).get("wallet", {})
        ticker = cfg.get("token", {}).get("ticker", "KAIG")
        return (
            f"WALLET INTELLIGENCE DIRECTIVE from ${ticker} Bridge:\n"
            f"PRIMARY GOAL: {goals.get('primary_goal', 'Track treasury and liquidity')}\n"
            f"SPEED: {goals.get('speed_mandate', 'Near real-time updates')}\n"
            f"TREASURY: ${self._treasury_reserves_usd:.2f} in reserves\n"
            f"${ticker} PRICE: ${self._kaig_price:.4f}\n"
            f"ACTION: Monitor all wallets. Alert on low reserves. "
            f"Treasury health is critical for ${ticker} stability."
        )

    def get_status(self) -> Dict:
        """Get bridge status."""
        return {
            "active": self._running,
            "cycle": self._cycle_count,
            "trading_profit_today_usd": self._trading_profit_today_usd,
            "mining_rewards_today_usd": self._mining_rewards_today_usd,
            "treasury_reserves_usd": self._treasury_reserves_usd,
            "kaig_price": self._kaig_price,
            "total_buybacks": self._total_buybacks,
            "config_loaded": self._cfg is not None,
        }
