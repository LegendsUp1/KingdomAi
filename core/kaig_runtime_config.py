"""
KAIG Runtime Configuration — Hot-Reloadable Singleton
=====================================================

SOLVES THE DEPLOYMENT DILEMMA:
  - All KAIG parameters loaded from config/kaig/runtime_config.json
  - Environment variables override JSON values (for deployed apps)
  - File watcher detects changes and hot-reloads without restart
  - Consumer apps can swap coin name, prices, contract addresses at runtime
  - No redeployment needed — change the JSON, system adapts instantly

Usage:
    from core.kaig_runtime_config import KAIGConfig
    cfg = KAIGConfig.get()

    # Access any value:
    cfg.ticker          # "KAIG"
    cfg.name            # "KAI Gold"
    cfg.total_supply    # 100_000_000
    cfg.target_price    # 10.00
    cfg.get("buyback.trading_profit_rate")  # 0.50

    # Force reload from disk:
    KAIGConfig.reload()

    # Change at runtime (persists to JSON):
    KAIGConfig.set("token.ticker", "NEWNAME")
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("KingdomAI.KAIG.Config")

_CONFIG_PATH = os.path.join("config", "kaig", "runtime_config.json")

# Environment variable prefix — KAIG_TOKEN_TICKER overrides token.ticker
_ENV_PREFIX = "KAIG_"


class KAIGConfig:
    """Singleton runtime configuration for the KAIG coin system.

    All KAIG parameters are stored in config/kaig/runtime_config.json.
    Environment variables with the KAIG_ prefix override JSON values.
    A background thread watches for file changes and hot-reloads.
    """

    _instance: Optional["KAIGConfig"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._file_mtime: float = 0.0
        self._watcher_running = False
        self._watcher_thread: Optional[threading.Thread] = None
        self._load()
        self._start_watcher()

    # ── SINGLETON ────────────────────────────────────────────────

    @classmethod
    def get(cls) -> "KAIGConfig":
        """Get the singleton config instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reload(cls):
        """Force reload config from disk."""
        inst = cls.get()
        inst._load()
        logger.info("KAIG runtime config reloaded from disk")

    @classmethod
    def set(cls, dotpath: str, value: Any, persist: bool = True):
        """Set a config value at runtime. Optionally persists to JSON.

        Args:
            dotpath: Dot-separated path, e.g. "token.ticker"
            value: New value
            persist: If True, writes back to runtime_config.json
        """
        inst = cls.get()
        keys = dotpath.split(".")
        d = inst._data
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        old = d.get(keys[-1])
        d[keys[-1]] = value
        logger.info("KAIG config SET %s: %s → %s", dotpath, old, value)

        if persist:
            inst._save()

        # Invalidate cached properties
        inst._invalidate_cache()

    # ── ACCESSORS ────────────────────────────────────────────────

    def get_value(self, dotpath: str, default: Any = None) -> Any:
        """Get a config value by dot-separated path.

        Environment variable override: KAIG_TOKEN_TICKER overrides token.ticker
        """
        # Check env var first
        env_key = _ENV_PREFIX + dotpath.upper().replace(".", "_")
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return self._coerce(env_val, default)

        # Walk the JSON tree
        keys = dotpath.split(".")
        d = self._data
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k)
            else:
                return default
            if d is None:
                return default
        return d

    def __getattr__(self, name: str) -> Any:
        """Convenience: cfg.ticker → cfg.get_value("token.ticker")"""
        # Shortcut mappings for the most commonly used values
        shortcuts = {
            # Token identity
            "ticker": "token.ticker",
            "name": "token.name",
            "full_name": "token.full_name",
            "description": "token.description",
            # Tokenomics
            "total_supply": "tokenomics.total_supply",
            "escrow_supply": "tokenomics.escrow_supply",
            "treasury_supply": "tokenomics.treasury_supply",
            "community_supply": "tokenomics.community_supply",
            "team_supply": "tokenomics.team_supply",
            "monthly_escrow_release": "tokenomics.monthly_escrow_release",
            "escrow_relock_rate": "tokenomics.escrow_relock_rate",
            "target_price": "tokenomics.target_price",
            "initial_price": "tokenomics.initial_price",
            "transaction_burn_rate": "tokenomics.transaction_burn_rate",
            # Buyback
            "trading_profit_buyback_rate": "buyback.trading_profit_rate",
            "min_buyback_threshold_usd": "buyback.min_threshold_usd",
            "buyback_cooldown_hours": "buyback.cooldown_hours",
            # Node
            "node_reward_per_hour": "node_rewards.reward_per_hour",
            "node_reward_cap_daily": "node_rewards.reward_cap_daily",
            "staking_apy": "node_rewards.staking_apy",
            # Speed
            "speed_policy": "speed_policy",
            # Deployment
            "deployment_mode": "deployment.mode",
            "on_chain_deployed": "deployment.on_chain_deployed",
            "contract_addresses": "deployment.contract_addresses",
            # Intelligence goals
            "trading_goals": "intelligence_goals.trading",
            "mining_goals": "intelligence_goals.mining",
            "wallet_goals": "intelligence_goals.wallet",
        }
        if name in shortcuts:
            return self.get_value(shortcuts[name])
        if name.startswith("_"):
            raise AttributeError(name)
        # Try direct dotpath
        val = self.get_value(name)
        if val is not None:
            return val
        raise AttributeError(f"KAIGConfig has no attribute '{name}'")

    @property
    def net_monthly_release(self) -> int:
        return int(self.monthly_escrow_release * (1 - self.escrow_relock_rate))

    @property
    def config_dir(self) -> str:
        return self.get_value("paths.config_dir", "config/kaig")

    @property
    def ledger_path(self) -> str:
        return self.get_value("paths.ledger", "config/kaig/ledger.json")

    @property
    def escrow_path(self) -> str:
        return self.get_value("paths.escrow", "config/kaig/escrow.json")

    @property
    def treasury_path(self) -> str:
        return self.get_value("paths.treasury", "config/kaig/treasury.json")

    @property
    def node_path(self) -> str:
        return self.get_value("paths.nodes", "config/kaig/nodes.json")

    @property
    def buyback_log_path(self) -> str:
        return self.get_value("paths.buyback_log", "config/kaig/buyback_log.json")

    def get_full_dict(self) -> Dict[str, Any]:
        """Return a deep copy of the full config dict."""
        import copy
        return copy.deepcopy(self._data)

    # ── INTERNAL ─────────────────────────────────────────────────

    def _load(self):
        """Load config from JSON file."""
        try:
            if os.path.exists(_CONFIG_PATH):
                with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                self._file_mtime = os.path.getmtime(_CONFIG_PATH)
                logger.info("KAIG runtime config loaded: ticker=%s, supply=%s, target=$%s",
                           self.get_value("token.ticker", "?"),
                           self.get_value("tokenomics.total_supply", "?"),
                           self.get_value("tokenomics.target_price", "?"))
            else:
                logger.warning("KAIG runtime config not found at %s — using defaults", _CONFIG_PATH)
                self._data = self._defaults()
                self._save()
        except Exception as e:
            logger.error("Failed to load KAIG runtime config: %s", e)
            self._data = self._defaults()

    def _save(self):
        """Persist current config to JSON."""
        try:
            os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4)
            self._file_mtime = os.path.getmtime(_CONFIG_PATH)
            logger.debug("KAIG runtime config saved to %s", _CONFIG_PATH)
        except Exception as e:
            logger.error("Failed to save KAIG runtime config: %s", e)

    def _defaults(self) -> Dict[str, Any]:
        """Hardcoded defaults — used only if JSON is missing."""
        return {
            "token": {"ticker": "KAIG", "name": "KAI Gold",
                      "full_name": "$KAIG (KAI Gold)",
                      "description": "AI-managed cryptocurrency"},
            "tokenomics": {"total_supply": 100_000_000, "escrow_supply": 70_000_000,
                           "treasury_supply": 15_000_000, "community_supply": 10_000_000,
                           "team_supply": 5_000_000, "monthly_escrow_release": 500_000,
                           "escrow_relock_rate": 0.75, "target_price": 10.00,
                           "initial_price": 0.10, "transaction_burn_rate": 0.001},
            "buyback": {"trading_profit_rate": 0.50, "min_threshold_usd": 10.0,
                        "cooldown_hours": 1},
            "node_rewards": {"reward_per_hour": 0.5, "reward_cap_daily": 12.0,
                             "staking_apy": 0.08},
            "speed_policy": {"intelligence_cycle_seconds": 10,
                             "event_throttle_seconds": 2},
            "deployment": {"mode": "pre_launch", "on_chain_deployed": False},
            "paths": {"config_dir": "config/kaig",
                      "ledger": "config/kaig/ledger.json",
                      "escrow": "config/kaig/escrow.json",
                      "treasury": "config/kaig/treasury.json"},
        }

    def _invalidate_cache(self):
        """Clear any cached computed values."""
        try:
            if hasattr(self, '_computed_cache'):
                self._computed_cache.clear()
            if hasattr(self, '_property_cache'):
                self._property_cache.clear()
            self._computed_cache = {}
            logger.debug("KAIG runtime config cache invalidated")
        except Exception as e:
            logger.debug("Error invalidating config cache: %s", e)

    def _start_watcher(self):
        """Start background file watcher for hot-reload."""
        if self._watcher_running:
            return
        self._watcher_running = True
        self._watcher_thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="KAIG-ConfigWatcher"
        )
        self._watcher_thread.start()

    def _watch_loop(self):
        """Poll for config file changes every 5 seconds."""
        while self._watcher_running:
            try:
                time.sleep(5)
                if os.path.exists(_CONFIG_PATH):
                    mtime = os.path.getmtime(_CONFIG_PATH)
                    if mtime > self._file_mtime:
                        logger.info("KAIG runtime config changed on disk — hot-reloading")
                        self._load()
            except Exception:
                pass

    @staticmethod
    def _coerce(value: str, reference: Any) -> Any:
        """Coerce a string env var to match the type of the reference value."""
        if reference is None:
            return value
        if isinstance(reference, bool):
            return value.lower() in ("true", "1", "yes")
        if isinstance(reference, int):
            try:
                return int(value)
            except ValueError:
                return reference
        if isinstance(reference, float):
            try:
                return float(value)
            except ValueError:
                return reference
        return value

    def stop(self):
        """Stop the file watcher."""
        self._watcher_running = False
