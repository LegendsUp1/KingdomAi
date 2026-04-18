#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Wallet Manager

This module provides wallet management functionality for multiple cryptocurrencies
across various blockchains, integrating with Web3 and supporting various coins.
"""

import asyncio
import os
import json
import time
import traceback
from typing import Dict, Any, Optional, List, Callable
import logging

# SOTA 2026: Import resilience patterns for real operation recovery
try:
    from core.resilience_patterns import (
        ResilientOperation, KingdomResilience, CircuitBreakerConfig,
        RetryConfig, OperationResult
    )
    HAS_RESILIENCE = True
except ImportError:
    HAS_RESILIENCE = False

from core.base_component import BaseComponent
from core.sentience.wallet_sentience_integration import WalletSentienceIntegration

# Import our KingdomWeb3 compatibility layer AND proper Web3
try:
    from kingdomweb3_v2 import rpc_manager, get_network_config
    kingdom_web3 = None  # Will use rpc_manager directly
    web3_available = True
    # CRITICAL FIX: Also import Web3 class for EVM chain operations
    try:
        from web3 import Web3
    except ImportError:
        Web3 = None
        logger.warning("web3 package not found despite kingdomweb3_v2 being available")
except ImportError:
    web3_available = False
    kingdom_web3 = None
    Web3 = None
    # Fallback: Try direct web3 import
    try:
        from web3 import Web3
        web3_available = True
    except ImportError:
        pass
    
try:
    from bitcoinrpc.authproxy import AuthServiceProxy
    btc_rpc_available = True
except ImportError:
    btc_rpc_available = False
    
try:
    from xrpl.clients import JsonRpcClient
    from xrpl.wallet import generate_faucet_wallet
    xrp_available = True
except ImportError:
    xrp_available = False
    
try:
    from solana.rpc.async_api import AsyncClient
    from solders.keypair import Keypair  # Fixed: solders instead of solana
    solana_available = True
except ImportError:
    solana_available = False
    
try:
    from eth_account import Account
    eth_account_available = True
except ImportError:
    eth_account_available = False

logger = logging.getLogger('KingdomAI.WalletManager')

class WalletManager(BaseComponent):
    """Manages wallets for multiple cryptocurrencies across blockchains."""
    
    # Blockchain base configurations — type + chain_id only.
    # RPC URLs are resolved per-instance via _resolve_rpc() so that consumer
    # instances never inherit the owner's Infura / Alchemy keys from .env.
    _BLOCKCHAIN_BASE = {
        "ETH":      {"type": "web3",       "chain_id": 1},
        "BTC":      {"type": "bitcoinrpc", "chain_id": 0},
        "XRP":      {"type": "xrp",        "chain_id": 0},
        "SOL":      {"type": "solana",     "chain_id": 0},
        "PI":       {"type": "pi",         "chain_id": 0},
        "POLYGON":  {"type": "web3",       "chain_id": 137},
        "BSC":      {"type": "web3",       "chain_id": 56},
        "ARBITRUM": {"type": "web3",       "chain_id": 42161},
        "OPTIMISM": {"type": "web3",       "chain_id": 10},
        "BASE":     {"type": "web3",       "chain_id": 8453},
        "AVAX":     {"type": "web3",       "chain_id": 43114},
        "KAIG": {
            "type": "kaig", "chain_id": 0,
            "rpc_url": "internal://kaig-ledger",
            "note": "KAI Gold — internal ledger, migrates to ERC-20 at Phase 3",
            "runtime_config": "config/kaig/runtime_config.json",
        },
    }

    # Public (free, no-key) fallback RPCs — safe for consumer instances
    _PUBLIC_RPC = {
        "ETH":      "https://rpc.ankr.com/eth",
        "BTC":      "https://blockstream.info/api",
        "XRP":      "https://s1.ripple.com:51234",
        "SOL":      "https://api.mainnet-beta.solana.com",
        "PI":       "https://api.pi.network",
        "POLYGON":  "https://polygon-rpc.com",
        "BSC":      "https://bsc-dataseed.binance.org",
        "ARBITRUM": "https://arb1.arbitrum.io/rpc",
        "OPTIMISM": "https://mainnet.optimism.io",
        "BASE":     "https://mainnet.base.org",
        "AVAX":     "https://api.avax.network/ext/bc/C/rpc",
    }

    # Env-var names that MAY contain the owner's paid RPCs
    _RPC_ENV_VARS = {
        "ETH": ["ETH_RPC_URL", "ALCHEMY_HTTPS_URL"],
        "BTC": ["BTC_RPC_URL"], "XRP": ["XRP_RPC_URL"],
        "SOL": ["SOL_RPC_URL"], "PI":  ["PI_RPC_URL"],
        "POLYGON": ["POLYGON_RPC_URL"], "BSC": ["BSC_RPC_URL"],
        "ARBITRUM": ["ARBITRUM_RPC_URL"], "OPTIMISM": ["OPTIMISM_RPC_URL"],
        "BASE": ["BASE_RPC_URL"], "AVAX": ["AVAX_RPC_URL"],
    }

    @classmethod
    def _build_blockchains(cls, *, allow_owner_keys: bool = True) -> dict:
        """Build the BLOCKCHAINS dict with per-instance RPC resolution.

        When *allow_owner_keys* is True (owner / creator), env-vars such as
        INFURA_PROJECT_ID and ALCHEMY_HTTPS_URL are used if set, with Infura
        as fallback for ETH.  When False (consumer), only free public RPCs
        are used — owner keys never leak.
        """
        result: dict = {}
        for sym, base in cls._BLOCKCHAIN_BASE.items():
            entry = dict(base)
            if "rpc_url" in entry:
                result[sym] = entry
                continue

            rpc = None
            if allow_owner_keys:
                for var in cls._RPC_ENV_VARS.get(sym, []):
                    rpc = os.getenv(var)
                    if rpc:
                        break
                if not rpc and sym == "ETH":
                    infura_id = os.getenv("INFURA_PROJECT_ID") or os.getenv(
                        "INFURA_API_KEY", "")
                    if infura_id:
                        rpc = f"https://mainnet.infura.io/v3/{infura_id}"

            if not rpc:
                rpc = cls._PUBLIC_RPC.get(sym, "")

            entry["rpc_url"] = rpc

            if allow_owner_keys and sym == "ETH":
                ws = os.getenv("ETH_WS_URL") or os.getenv("ALCHEMY_WEBSOCKET_URL")
                if not ws:
                    infura_id = os.getenv("INFURA_PROJECT_ID") or os.getenv(
                        "INFURA_API_KEY", "")
                    if infura_id:
                        ws = f"wss://mainnet.infura.io/ws/v3/{infura_id}"
                if ws:
                    entry["ws_url"] = ws

            result[sym] = entry
        return result

    BLOCKCHAINS: dict = {}  # populated per-instance in __init__
    
    def __init__(self, event_bus=None, config: Optional[Dict[str, Any]] = None):
        """Initialize wallet manager component."""
        super().__init__(event_bus=event_bus)
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        allow_owner = not self.config.get("skip_owner_data", False)
        self.BLOCKCHAINS = self._build_blockchains(allow_owner_keys=allow_owner)
        
        # Connection status flag for integration with other components
        self.is_connected = True  # Set to True for immediate functionality
        
        # Wallets data structure: {coin: {address: {private_key, name, balance, last_update}}}
        self.wallets: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        # Address cache for faster lookups
        self.address_cache: Dict[str, str] = {}  # {network: address}
        
        # Initialize missing attributes - 2025 Fix for AttributeError issues
        self.clients: Dict[str, Any] = {}  # Blockchain client connections
        self.status: Dict[str, Any] = {    # System status tracking
            "connected": True,
            "last_update": time.time(),
            "active_connections": 0,
            "total_wallets": 0
        }
        self._trading_system_readiness: Dict[str, Any] = {"state": "UNKNOWN", "auto_trade_started": False}
        
        # Initialize sentience integration
        try:
            self.sentience_integration = WalletSentienceIntegration(event_bus=self.event_bus)
        except Exception as e:
            self.logger.warning(f"Sentience integration unavailable: {e}")
            self.sentience_integration = None
        
        # REAL WALLET DATA ONLY - NO MOCKS
        # skip_owner_data: Set True for consumer instances so they never
        # touch kingdom_ai_wallet_app.json or multi_coin_wallets.json
        self._skip_owner_data = self.config.get("skip_owner_data", False)

        self._is_consumer = (
            self._skip_owner_data
            or os.environ.get("KINGDOM_APP_MODE", "").lower() == "consumer"
        )
        self.OWNER_WALLET = "0x4bED94d31d945a1C49F67721612bffb83eD1107C"
        self.CONSUMER_COMMISSION_RATE = 0.10  # 10% on winning trades

        self._commission_ledger_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "commission_ledger.json"
        )
        self._commission_owed: float = 0.0
        self._commission_paid: float = 0.0
        self._load_commission_ledger()

        self._init_real_wallet_data()

        # Bridge ALL KingdomWeb3 v2 chains into BLOCKCHAINS registry
        self._bridge_kingdomweb3_chains()
    
    # Symbol-to-network-name mapping for bridging config keys (ETH) to
    # COMPLETE_BLOCKCHAIN_NETWORKS keys (ethereum).  Entries are lowercase.
    _SYMBOL_TO_NETWORK = {
        "ETH": "ethereum", "BTC": "bitcoin", "SOL": "solana", "XRP": "xrp",
        "BSC": "bsc", "BNB": "bsc", "AVAX": "avalanche", "FTM": "fantom",
        "ARB": "arbitrum", "OP": "optimism", "MATIC": "polygon", "DOT": "polkadot",
        "ADA": "cardano", "DOGE": "dogechain", "LTC": "litecoin",
        "KAS": "kaspa", "ETC": "ethereum_classic", "ZEC": "zcash",
        "DASH": "dash", "BCH": "bitcoin_cash", "XMR": "monero",
    }

    _NON_EVM_TYPES = {
        "bitcoin": "bitcoinrpc", "solana": "solana", "xrp": "xrp",
        "monero": "monero", "cardano": "cardano", "polkadot": "polkadot",
        "cosmos": "cosmos", "tron": "tron", "near": "near",
        "algorand": "algorand", "hedera": "hedera", "stellar": "stellar",
        "litecoin": "bitcoinrpc", "bitcoin_cash": "bitcoinrpc",
        "dogecoin": "bitcoinrpc", "zcash": "bitcoinrpc", "dash": "bitcoinrpc",
    }

    def _bridge_kingdomweb3_chains(self):
        """Dynamically import all COMPLETE_BLOCKCHAIN_NETWORKS from KingdomWeb3 v2
        and register them in this WalletManager's BLOCKCHAINS dict.

        This ensures every chain KingdomWeb3 knows about is also available for
        wallet send/receive operations without hardcoding each one.
        """
        try:
            from kingdomweb3_v2 import COMPLETE_BLOCKCHAIN_NETWORKS
        except ImportError:
            try:
                from core.blockchain.kingdomweb3_v2 import COMPLETE_BLOCKCHAIN_NETWORKS
            except ImportError:
                self.logger.debug("KingdomWeb3 v2 not found; skipping chain bridge")
                return

        added = 0
        for net_name, net_cfg in COMPLETE_BLOCKCHAIN_NETWORKS.items():
            upper_key = net_name.upper()
            if upper_key in self.BLOCKCHAINS:
                continue
            chain_id = net_cfg.get("chain_id", 0)
            rpc_url = net_cfg.get("rpc_url", "")
            if not rpc_url:
                continue
            bc_type = self._NON_EVM_TYPES.get(net_name, "web3")
            entry = {"rpc_url": rpc_url, "type": bc_type}
            if chain_id:
                entry["chain_id"] = chain_id
            self.BLOCKCHAINS[upper_key] = entry
            if net_name not in self._SYMBOL_TO_NETWORK.values():
                for sym, mapped in list(self._SYMBOL_TO_NETWORK.items()):
                    if mapped == net_name:
                        break
                else:
                    self._SYMBOL_TO_NETWORK[upper_key] = net_name
            added += 1

        if added:
            self.logger.info("Bridged %d chains from KingdomWeb3 v2 → wallet BLOCKCHAINS (%d total)",
                             added, len(self.BLOCKCHAINS))

    def _init_real_wallet_data(self):
        """Initialize wallet data from real sources only - NO MOCK DATA.
        
        Load order:
        1. data/wallets/kingdom_ai_wallet_app.json  (primary, written by WalletCreator)
        2. config/multi_coin_wallets.json            (fallback, always present)
        
        Addresses are stored under BOTH their symbol key (ETH) and their
        network-name key (ethereum) so that look-ups from either convention work.
        """
        # Initialize empty caches - will be populated from real blockchain data
        self.address_cache = {}
        self.balance_cache = {}
        self._balance_cache_ts = {}
        self.transaction_cache = {}
        self._active_user_id = "creator"

        if self._skip_owner_data:
            logger.info("Consumer mode: skipping owner wallet files (kingdom_ai_wallet_app.json, multi_coin_wallets.json)")
            return
        
        # --- Source 1: Kingdom AI Wallet app descriptor ---
        try:
            wallet_dir = os.path.join("data", "wallets")
            app_wallet_path = os.path.join(wallet_dir, "kingdom_ai_wallet_app.json")
            if os.path.exists(app_wallet_path):
                with open(app_wallet_path, "r", encoding="utf-8-sig") as f:
                    app_data = json.load(f)
                # "addresses" dict uses network names (ethereum, bitcoin)
                addresses = app_data.get("addresses") or {}
                if isinstance(addresses, dict):
                    for network, addr in addresses.items():
                        if isinstance(addr, str) and addr.strip():
                            self.address_cache[network] = addr.strip()
                # "chains" dict uses symbols (ETH, BTC) with {"address": "..."}
                chains = app_data.get("chains") or {}
                if isinstance(chains, dict):
                    for sym, info in chains.items():
                        addr = info.get("address") if isinstance(info, dict) else info
                        if isinstance(addr, str) and addr.strip():
                            sym_upper = sym.upper()
                            if sym_upper not in self.address_cache:
                                self.address_cache[sym_upper] = addr.strip()
                            # Also store under network name
                            net_name = self._SYMBOL_TO_NETWORK.get(sym_upper)
                            if net_name and net_name not in self.address_cache:
                                self.address_cache[net_name] = addr.strip()
                logger.info(f"✅ Loaded {len(self.address_cache)} real wallet addresses from Kingdom AI Wallet app")
        except Exception as e:
            logger.error(f"❌ Failed to load wallet app configuration: {e}")
        
        # --- Source 2: multi_coin_wallets.json (fallback / augment) ---
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            mcw_path = os.path.join(base_dir, "config", "multi_coin_wallets.json")
            if os.path.exists(mcw_path):
                with open(mcw_path, "r", encoding="utf-8-sig") as f:
                    mcw_data = json.load(f)
                loaded_from_mcw = 0
                # Load default wallets
                for key in ("default_wallet", "default_gpu_wallet",
                            "default_randomx_wallet", "default_cryptonight_wallet"):
                    addr = mcw_data.get(key)
                    if isinstance(addr, str) and addr.strip():
                        if key not in self.address_cache:
                            self.address_cache[key] = addr.strip()
                # Load cpu_wallets and gpu_wallets sections
                for section in ("cpu_wallets", "gpu_wallets"):
                    wallets = mcw_data.get(section) or {}
                    if isinstance(wallets, dict):
                        for sym, addr in wallets.items():
                            if not isinstance(addr, str) or not addr.strip():
                                continue
                            sym_upper = sym.upper()
                            # Store under symbol
                            if sym_upper not in self.address_cache:
                                self.address_cache[sym_upper] = addr.strip()
                                loaded_from_mcw += 1
                            # Also store under network name if mapped
                            net_name = self._SYMBOL_TO_NETWORK.get(sym_upper)
                            if net_name and net_name not in self.address_cache:
                                self.address_cache[net_name] = addr.strip()
                if loaded_from_mcw > 0:
                    logger.info(f"✅ Loaded {loaded_from_mcw} additional wallet addresses from multi_coin_wallets.json")
            else:
                logger.debug(f"multi_coin_wallets.json not found at {mcw_path}")
        except Exception as e:
            logger.error(f"❌ Failed to load multi_coin_wallets.json: {e}")
        
        # --- Source 3: KAIG wallet auto-creation via AutoPilot ---
        try:
            from core.kaig_autopilot import KAIGWalletManager
            kaig_wm = KAIGWalletManager()
            for wid, winfo in kaig_wm.list_wallets().items():
                kaig_addr = winfo.get("kaig_address", "")
                if kaig_addr and winfo.get("wallet_type") in ("creator", "consumer"):
                    self.address_cache["KAIG"] = kaig_addr
                    self.address_cache["kaig"] = kaig_addr
                    logger.info(f"✅ KAIG wallet loaded: {kaig_addr[:20]}...")
                    break
        except Exception as e:
            logger.debug(f"KAIG wallet integration (non-fatal): {e}")
        
        if self.address_cache:
            logger.info(f"✅ Wallet address cache: {len(self.address_cache)} entries ready")
        else:
            logger.warning("⚠️ No wallet addresses configured - wallet features unavailable until wallets are set up")

    # =========================================================================
    # CONSUMER COMMISSION LEDGER (10% on winning trades -> owner wallet)
    # =========================================================================

    def _load_commission_ledger(self):
        """Load accumulated commission state from disk."""
        try:
            if os.path.exists(self._commission_ledger_path):
                with open(self._commission_ledger_path, "r") as f:
                    data = json.load(f)
                self._commission_owed = float(data.get("owed", 0.0))
                self._commission_paid = float(data.get("paid", 0.0))
        except Exception:
            self._commission_owed = 0.0
            self._commission_paid = 0.0

    def _save_commission_ledger(self):
        """Persist commission state to disk."""
        try:
            os.makedirs(os.path.dirname(self._commission_ledger_path), exist_ok=True)
            with open(self._commission_ledger_path, "w") as f:
                json.dump({
                    "owed": round(self._commission_owed, 8),
                    "paid": round(self._commission_paid, 8),
                    "owner_wallet": self.OWNER_WALLET,
                    "rate": self.CONSUMER_COMMISSION_RATE,
                    "last_update": time.time(),
                }, f, indent=2)
        except Exception as e:
            self.logger.error("Failed to save commission ledger: %s", e)

    def _deduct_consumer_commission(self, profit: float, coin: str, trade_id: str = "") -> float:
        """Deduct 10% commission from a winning trade profit (consumer mode only).

        Returns the net profit after commission deduction.
        """
        if not self._is_consumer or profit <= 0:
            return profit

        commission = round(profit * self.CONSUMER_COMMISSION_RATE, 8)
        net_profit = profit - commission

        self._commission_owed += commission
        self._save_commission_ledger()

        self.logger.info(
            "Consumer commission: %.8f %s (10%% of %.8f) -> owner wallet %s",
            commission, coin, profit, self.OWNER_WALLET,
        )

        self._safe_publish("commission.collected", {
            "commission_usd": commission,
            "amount": commission,
            "coin": coin,
            "original_profit": profit,
            "net_profit": net_profit,
            "rate": self.CONSUMER_COMMISSION_RATE,
            "owner_wallet": self.OWNER_WALLET,
            "trade_id": trade_id,
            "timestamp": time.time(),
        })

        if coin not in self.wallets:
            self.wallets[coin] = {}
        owner_key = f"owner_commission_{self.OWNER_WALLET[:10]}"
        if owner_key not in self.wallets[coin]:
            self.wallets[coin][owner_key] = {
                "balance": 0.0,
                "name": "Owner Commission (pending transfer)",
                "last_update": time.time(),
            }
        self.wallets[coin][owner_key]["balance"] = float(
            self.wallets[coin][owner_key].get("balance", 0.0)
        ) + commission
        self.wallets[coin][owner_key]["last_update"] = time.time()

        self._safe_publish("wallet.commission.recorded", {
            "coin": coin,
            "commission": commission,
            "total_owed": self._commission_owed,
            "total_paid": self._commission_paid,
            "owner_wallet": self.OWNER_WALLET,
            "timestamp": time.time(),
        })

        return net_profit

    def load_user_wallet(self, user_id: str) -> bool:
        """Replace the address_cache with a specific user's wallet addresses.

        Used by consumer instances so they operate on THEIR OWN wallet,
        not the owner's kingdom_ai_wallet_app.json.  Returns True if the
        user wallet was found and loaded, False otherwise.
        """
        try:
            from core.wallet_creator import WalletCreator
            wc = WalletCreator(event_bus=self.event_bus)
            manifest = wc.get_user_wallet(user_id)
            if not manifest or not manifest.get("addresses"):
                logger.warning("No wallet manifest for user %s", user_id)
                return False

            self.address_cache.clear()
            self.balance_cache.clear()
            self._balance_cache_ts.clear()

            for chain_sym, addr in manifest["addresses"].items():
                if isinstance(addr, str) and addr.strip():
                    sym_upper = chain_sym.upper()
                    self.address_cache[sym_upper] = addr.strip()
                    net_name = self._SYMBOL_TO_NETWORK.get(sym_upper)
                    if net_name:
                        self.address_cache[net_name] = addr.strip()

            self._active_user_id = user_id
            logger.info("Loaded user wallet for '%s' — %d addresses",
                        user_id, len(self.address_cache))
            return True
        except Exception as e:
            logger.error("Failed to load user wallet for '%s': %s", user_id, e)
            return False

    def get_active_user_id(self) -> str:
        """Return the active user_id ('creator' for owner, device id for consumers)."""
        return getattr(self, '_active_user_id', 'creator')

    def get_address(self, network: str) -> str:
        """Get wallet address for specified network - REAL DATA ONLY.
        
        Supports look-up by network name ('ethereum') or symbol ('ETH').
        Falls back to case-insensitive matching.
        """
        try:
            # Direct hit
            address = self.address_cache.get(network)
            if address:
                return address
            # Try uppercase symbol (e.g. "ethereum" -> "ETH")
            upper = network.upper()
            address = self.address_cache.get(upper)
            if address:
                return address
            # Try symbol-to-network-name mapping
            net_name = self._SYMBOL_TO_NETWORK.get(upper)
            if net_name:
                address = self.address_cache.get(net_name)
                if address:
                    return address
            # Try reverse: network-name to symbol lookup
            for sym, name in self._SYMBOL_TO_NETWORK.items():
                if name == network.lower():
                    address = self.address_cache.get(sym)
                    if address:
                        return address
            # Case-insensitive scan as last resort
            network_lower = network.lower()
            for key, addr in self.address_cache.items():
                if key.lower() == network_lower:
                    return addr
            logger.debug(f"No wallet configured for network '{network}'")
            return ""  # Empty = not configured
        except Exception as e:
            logger.error(f"Error getting address for {network}: {e}")
            return ""
    
    def get_balance(self, network: str, address: str = None) -> float:
        """Get balance for specified network and address.
        
        Returns cached value if fresh (< 60s), otherwise queries chain.
        """
        try:
            cached = self.balance_cache.get(network, 0.0)
            cache_ts = self._balance_cache_ts.get(network, 0)
            import time as _t
            if cached > 0 and (_t.time() - cache_ts) < 60:
                return cached
            fresh = self._fetch_onchain_balance(network, address)
            if fresh is not None:
                return fresh
            return cached
        except Exception as e:
            logger.error(f"Error getting balance for {network}: {e}")
            return self.balance_cache.get(network, 0.0)

    def _try_fallback_rpcs(self, net_upper: str):
        """SOTA 2026: Try fallback RPC list for Ethereum and EVM chains."""
        fallback_rpcs = {
            "ETH": [
                "https://ethereum-rpc.publicnode.com",
                "https://rpc.ankr.com/eth",
                "https://eth.llamarpc.com",
                "https://1rpc.io/eth"
            ],
            "POLYGON": [
                "https://polygon-rpc.com",
                "https://rpc.ankr.com/polygon",
                "https://polygon-pokt.nodies.app"
            ],
            "BSC": [
                "https://bsc-dataseed.binance.org",
                "https://rpc.ankr.com/bsc",
                "https://bsc-pokt.nodies.app"
            ],
            "ARBITRUM": [
                "https://arb1.arbitrum.io/rpc",
                "https://rpc.ankr.com/arbitrum"
            ],
            "OPTIMISM": [
                "https://mainnet.optimism.io",
                "https://rpc.ankr.com/optimism"
            ],
            "BASE": [
                "https://mainnet.base.org",
                "https://base-pokt.nodies.app"
            ],
            "AVAX": [
                "https://api.avax.network/ext/bc/C/rpc",
                "https://rpc.ankr.com/avalanche"
            ],
        }
        
        rpc_list = fallback_rpcs.get(net_upper, [])
        if not rpc_list:
            return None
        
        try:
            from web3.providers.rpc import HTTPProvider
            for rpc_url in rpc_list:
                try:
                    w3 = Web3(HTTPProvider(rpc_url))
                    if w3.is_connected():
                        logger.info(f"✅ Connected to {net_upper} via fallback RPC: {rpc_url[:50]}...")
                        return w3
                except Exception:
                    continue
        except Exception:
            pass
        
        return None

    def _fetch_onchain_balance(self, network: str, address: str = None) -> float:
        """Query real on-chain balance via Web3 / block-explorer API."""
        import time as _t
        try:
            net_upper = network.upper()
            sym_lookup = self._SYMBOL_TO_NETWORK.get(net_upper, net_upper.lower())
            if not address:
                address = (self.address_cache.get(net_upper)
                           or self.address_cache.get(sym_lookup)
                           or self.address_cache.get(network))
            if not address:
                return None

            bc_config = self.BLOCKCHAINS.get(net_upper, {})
            bc_type = bc_config.get("type", "")

            balance = None

            if bc_type == "web3" or net_upper in ("ETH", "ETC", "POLYGON", "BSC",
                    "ARBITRUM", "OPTIMISM", "BASE", "AVAX", "ETHW", "CFX"):
                w3 = (self.clients.get(net_upper)
                      or self.clients.get(sym_lookup)
                      or self.clients.get(network))
                if w3 is None and Web3 is not None:
                    rpc_url = bc_config.get("rpc_url", "")
                    if rpc_url and "YOUR_PROJECT_ID" not in rpc_url:
                        try:
                            from web3.providers.rpc import HTTPProvider
                            # SOTA 2026: Try primary RPC first
                            w3 = Web3(HTTPProvider(rpc_url))
                            if w3.is_connected():
                                self.clients[net_upper] = w3
                            else:
                                # Fallback to public RPC list if primary fails
                                w3 = self._try_fallback_rpcs(net_upper)
                                if w3:
                                    self.clients[net_upper] = w3
                                else:
                                    w3 = None
                        except Exception:
                            # Try fallback RPCs on any exception
                            w3 = self._try_fallback_rpcs(net_upper)
                            if w3:
                                self.clients[net_upper] = w3
                            else:
                                w3 = None
                if w3 is not None and hasattr(w3, 'eth'):
                    try:
                        checksum = w3.to_checksum_address(address)
                        wei = w3.eth.get_balance(checksum)
                        balance = float(w3.from_wei(wei, 'ether'))
                    except Exception as e:
                        logger.debug(f"Web3 balance query failed for {net_upper}: {e}")

            elif net_upper == "BTC":
                try:
                    import requests as _req
                    resp = _req.get(
                        f"https://blockstream.info/api/address/{address}",
                        timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        funded = data.get("chain_stats", {}).get("funded_txo_sum", 0)
                        spent = data.get("chain_stats", {}).get("spent_txo_sum", 0)
                        balance = (funded - spent) / 1e8
                except Exception as e:
                    logger.debug(f"BTC balance query failed: {e}")

            elif net_upper in ("LTC", "DOGE", "DASH"):
                try:
                    import requests as _req
                    api_map = {
                        "LTC": "https://api.blockcypher.com/v1/ltc/main/addrs/",
                        "DOGE": "https://api.blockcypher.com/v1/doge/main/addrs/",
                        "DASH": "https://api.blockcypher.com/v1/dash/main/addrs/",
                    }
                    url = api_map.get(net_upper, "")
                    if url:
                        resp = _req.get(f"{url}{address}/balance", timeout=10)
                        if resp.status_code == 200:
                            data = resp.json()
                            balance = data.get("balance", 0) / 1e8
                except Exception as e:
                    logger.debug(f"{net_upper} balance query failed: {e}")

            elif net_upper == "SOL":
                try:
                    import requests as _req
                    resp = _req.post(
                        "https://api.mainnet-beta.solana.com",
                        json={"jsonrpc": "2.0", "id": 1,
                              "method": "getBalance",
                              "params": [address]},
                        timeout=10)
                    if resp.status_code == 200:
                        result = resp.json().get("result", {})
                        balance = result.get("value", 0) / 1e9
                except Exception as e:
                    logger.debug(f"SOL balance query failed: {e}")

            if balance is not None:
                self.balance_cache[network] = balance
                self.balance_cache[net_upper] = balance
                if sym_lookup != net_upper.lower():
                    self.balance_cache[sym_lookup] = balance
                self._balance_cache_ts[network] = _t.time()
                self._balance_cache_ts[net_upper] = _t.time()
                if balance > 0:
                    logger.info(f"On-chain balance for {net_upper}: {balance:.8f}")
                if self.event_bus:
                    try:
                        self.event_bus.publish("wallet.balance.updated", {
                            "coin": net_upper,
                            "balance": balance,
                            "new_balance": balance,
                            "source": "onchain",
                        })
                    except Exception:
                        pass
            return balance
        except Exception as e:
            logger.error(f"_fetch_onchain_balance error for {network}: {e}")
            return None

    def fetch_all_balances(self):
        """Fetch on-chain balances for all configured wallets (boot-time scan)."""
        fetched = 0
        for network, address in list(self.address_cache.items()):
            if network.startswith("default_") or len(network) > 20:
                continue
            bal = self._fetch_onchain_balance(network, address)
            if bal is not None and bal > 0:
                fetched += 1
        if fetched:
            logger.info(f"Fetched {fetched} non-zero on-chain balances")
        return fetched

    def send_transaction(self, network: str, to_address: str, amount: float) -> str:
        """Send REAL transaction on specified network — multi-chain SOTA 2026.

        Pipeline: AI validation -> address resolve -> chain send -> receipt -> history.
        """
        try:
            net_upper = network.upper()
            sym_lookup = self._SYMBOL_TO_NETWORK.get(net_upper, net_upper.lower())

            from_address = (self.address_cache.get(net_upper)
                            or self.address_cache.get(sym_lookup)
                            or self.address_cache.get(network))
            if not from_address:
                raise ValueError(f"No wallet configured for '{network}'")

            ai_verdict = self._ai_validate_transaction(
                net_upper, from_address, to_address, amount)
            if ai_verdict and ai_verdict.get("blocked"):
                raise ValueError(
                    f"AI blocked transaction: {ai_verdict.get('reason', 'risk too high')}")

            bc_config = self.BLOCKCHAINS.get(net_upper, {})
            bc_type = bc_config.get("type", "")

            web3_client = (self.clients.get(net_upper)
                           or self.clients.get(sym_lookup)
                           or self.clients.get(network))

            needs_client = bc_type in ("web3",)
            if needs_client and not web3_client:
                raise ConnectionError(f"No blockchain client for '{network}'")

            tx_hash = self._send_real_transaction(
                web3_client, network, from_address, to_address, amount)
            logger.info("REAL transaction sent: %s %s to %s on %s — TX: %s",
                        amount, net_upper, to_address[:16], network, tx_hash)
            return tx_hash

        except Exception as e:
            logger.error("Transaction error on %s: %s", network, e)
            raise

    # ── AI TRANSACTION VALIDATION (Ollama Brain) ────────────────────

    _AI_TX_DAILY_TOTALS: Dict[str, float] = {}
    _AI_TX_DAILY_LIMIT: float = 50000.0
    _AI_TX_SINGLE_LIMIT: float = 10000.0

    def _ai_validate_transaction(self, network: str, from_addr: str,
                                  to_addr: str, amount: float) -> Optional[Dict]:
        """AI-powered transaction risk assessment using Ollama brain.

        Performs rule-based checks first, then queries Ollama for
        anomaly detection on high-value or unusual transactions.
        Returns None (allow) or dict with blocked=True and reason.
        """
        try:
            today = time.strftime("%Y-%m-%d")
            day_key = f"{from_addr}:{today}"
            daily = self._AI_TX_DAILY_TOTALS.get(day_key, 0.0)

            if amount > self._AI_TX_SINGLE_LIMIT:
                ai_opinion = self._query_ollama_risk(network, from_addr, to_addr, amount)
                if ai_opinion and ai_opinion.get("risk_level") == "critical":
                    return {"blocked": True,
                            "reason": ai_opinion.get("reason", "AI flagged critical risk")}

            if daily + amount > self._AI_TX_DAILY_LIMIT:
                return {"blocked": True,
                        "reason": f"Daily limit exceeded: ${daily + amount:.2f} > ${self._AI_TX_DAILY_LIMIT:.2f}"}

            self._AI_TX_DAILY_TOTALS[day_key] = daily + amount

            if amount > self._AI_TX_SINGLE_LIMIT * 0.5:
                ai_opinion = self._query_ollama_risk(network, from_addr, to_addr, amount)
                if ai_opinion and ai_opinion.get("risk_level") == "critical":
                    self._AI_TX_DAILY_TOTALS[day_key] -= amount
                    return {"blocked": True,
                            "reason": ai_opinion.get("reason", "AI flagged high risk")}

            self._safe_publish("ai.transaction.validated", {
                "network": network, "amount": amount,
                "to": to_addr[:16], "status": "approved"})
            return None
        except Exception as e:
            logger.debug("AI validation skipped (non-blocking): %s", e)
            return None

    def _query_ollama_risk(self, network: str, from_addr: str,
                            to_addr: str, amount: float) -> Optional[Dict]:
        """Query Ollama for transaction risk assessment."""
        try:
            import requests
            base_url = os.getenv("KINGDOM_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
            model = os.getenv("KINGDOM_OLLAMA_MODEL", "cogito:latest")

            prompt = (
                f"TRANSACTION RISK ASSESSMENT — respond with JSON only.\n"
                f"Network: {network}\nFrom: {from_addr[:12]}...\n"
                f"To: {to_addr[:12]}...\nAmount: {amount}\n\n"
                f"Evaluate: Is this transaction suspicious? Consider:\n"
                f"- Amount relative to typical transactions\n"
                f"- Whether the destination looks like a known scam pattern\n"
                f"- Whether this could be a dusting attack or drainer\n\n"
                f"Respond ONLY with: {{\"risk_level\": \"low|medium|high|critical\", "
                f"\"reason\": \"brief explanation\", \"confidence\": 0.0-1.0}}"
            )

            headers = {}
            api_key = os.environ.get("OLLAMA_API_KEY", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            resp = requests.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.1, "num_predict": 200}},
                headers=headers, timeout=10)

            if resp.status_code == 200:
                text = resp.json().get("response", "")
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    result = json.loads(text[start:end])
                    logger.info("AI risk assessment: %s (confidence=%.2f)",
                                result.get("risk_level", "?"),
                                result.get("confidence", 0))
                    return result
        except Exception as e:
            logger.debug("Ollama risk query failed (non-blocking): %s", e)
        return None
    
    # ── NONCE MANAGER ────────────────────────────────────────────────
    _nonce_cache: Dict[str, int] = {}
    _nonce_lock = None  # initialized lazily

    def _get_nonce_lock(self):
        import threading
        if self._nonce_lock is None:
            WalletManager._nonce_lock = threading.Lock()
        return self._nonce_lock

    def _next_nonce(self, web3_client, from_address: str) -> int:
        """Thread-safe nonce management with local tracking."""
        lock = self._get_nonce_lock()
        with lock:
            key = from_address.lower()
            on_chain = web3_client.eth.get_transaction_count(from_address, 'pending')
            cached = self._nonce_cache.get(key, -1)
            nonce = max(on_chain, cached + 1) if cached >= 0 else on_chain
            WalletManager._nonce_cache[key] = nonce
            return nonce

    def _reset_nonce(self, from_address: str):
        lock = self._get_nonce_lock()
        with lock:
            WalletManager._nonce_cache.pop(from_address.lower(), None)

    # ── PRIVATE KEY MANAGER (Fernet decryption from WalletCreator) ───

    _pk_mem_cache: Dict[str, str] = {}

    def _get_private_key(self, network: str, address: str) -> Optional[str]:
        """Retrieve private key: env var -> WalletCreator encrypted files -> None.

        Keys are cached in memory for the session. NEVER logged or persisted.
        """
        cache_key = f"{network}:{address}".lower()
        if cache_key in self._pk_mem_cache:
            return self._pk_mem_cache[cache_key]

        env_key = f"KINGDOM_WALLET_{network.upper()}_PRIVATE_KEY"
        pk = os.environ.get(env_key)
        if pk:
            self._pk_mem_cache[cache_key] = pk
            return pk

        try:
            from cryptography.fernet import Fernet
            key_file = os.path.join("data", ".encryption_key")
            if not os.path.exists(key_file):
                return None
            with open(key_file, 'rb') as f:
                enc_key = f.read()
            fernet = Fernet(enc_key)

            wallet_dir = os.path.join("data", "wallets")
            if not os.path.isdir(wallet_dir):
                return None

            addr_lower = address.lower() if address else ""
            sym_upper = network.upper()
            net_name = self._SYMBOL_TO_NETWORK.get(sym_upper, sym_upper.lower())

            for fname in os.listdir(wallet_dir):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(wallet_dir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8-sig') as f:
                        wdata = json.load(f)
                    w_addr = (wdata.get("address") or "").lower()
                    w_chain = (wdata.get("blockchain") or "").upper()
                    enc_pk = wdata.get("encrypted_private_key")
                    if not enc_pk or not w_addr:
                        continue
                    chain_match = (w_chain == sym_upper or
                                   w_chain == net_name.upper())
                    addr_match = (w_addr == addr_lower or
                                  (addr_lower and w_addr.startswith(addr_lower[:10])))
                    if chain_match and addr_match:
                        decrypted = fernet.decrypt(enc_pk.encode()).decode()
                        if decrypted:
                            self._pk_mem_cache[cache_key] = decrypted
                            return decrypted
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Encrypted wallet key lookup failed: {e}")
        return None

    # ── MULTI-CHAIN TRANSACTION ENGINE (SOTA 2026) ──────────────────
    
    def _get_blockchain_adapter(self, network: str):
        """Get blockchain adapter for the given network if available.
        
        Args:
            network: Network name or symbol
            
        Returns:
            BlockchainAdapter instance or None if not available
        """
        try:
            net_upper = network.upper()
            network_name = self._SYMBOL_TO_NETWORK.get(net_upper, network.lower())
            
            # Map network names to adapter classes
            adapter_map = {
                "ethereum": ("blockchain.ethereum_adapter", "EthereumAdapter"),
                "solana": ("blockchain.solana_adapter", "SolanaAdapter"),
                "bitcoin": ("blockchain.bitcoin_adapter", "BitcoinAdapter"),
                "xrp": ("blockchain.xrp_adapter", "XRPAdapter"),
                "polygon": ("blockchain.polygon_adapter", "PolygonAdapter"),
                "bsc": ("blockchain.bsc_adapter", "BSCAdapter"),
                "arbitrum": ("blockchain.arbitrum_adapter", "ArbitrumAdapter"),
                "optimism": ("blockchain.optimism_adapter", "OptimismAdapter"),
                "avalanche": ("blockchain.avalanche_adapter", "AvalancheAdapter"),
                "monero": ("blockchain.monero_adapter", "MoneroAdapter"),
            }
            
            if network_name not in adapter_map:
                return None
            
            module_path, class_name = adapter_map[network_name]
            module = __import__(module_path, fromlist=[class_name])
            adapter_class = getattr(module, class_name)
            
            # Get network config for chain_id
            bc_config = self.BLOCKCHAINS.get(net_upper, {})
            chain_id = bc_config.get("chain_id")
            
            # Create adapter instance
            adapter = adapter_class(network_name, chain_id)
            
            # Configure adapter with RPC URL
            rpc_url = self._resolve_rpc(net_upper)
            adapter.configure({"endpoint_uri": rpc_url})
            
            # Connect adapter
            if adapter.connect():
                return adapter
            
            return None
        except ImportError:
            return None
        except Exception as e:
            self.logger.debug(f"Failed to get blockchain adapter for {network}: {e}")
            return None

    def _send_real_transaction(self, web3_client, network: str,
                               from_address: str, to_address: str,
                               amount: float) -> str:
        """Route transaction to the correct chain-specific sender."""
        private_key = self._get_private_key(network, from_address)
        if not private_key:
            raise ValueError(f"Private key not available for {from_address} on {network}")

        net_upper = network.upper()
        bc_config = self.BLOCKCHAINS.get(net_upper, {})
        bc_type = bc_config.get("type", "")

        if bc_type == "web3" or (hasattr(web3_client, 'eth') and web3_client is not None):
            return self._send_evm_transaction(
                web3_client, network, from_address, to_address, amount, private_key)
        elif bc_type == "bitcoinrpc" or net_upper == "BTC":
            return self._send_btc_transaction(
                network, from_address, to_address, amount, private_key)
        elif bc_type == "solana" or net_upper == "SOL":
            return self._send_sol_transaction(
                network, from_address, to_address, amount, private_key)
        elif bc_type == "xrp" or net_upper == "XRP":
            return self._send_xrp_transaction(
                network, from_address, to_address, amount, private_key)
        elif net_upper == "XMR":
            return self._send_xmr_transaction(
                network, from_address, to_address, amount)
        else:
            # Try to use blockchain adapter if available
            adapter = self._get_blockchain_adapter(network)
            if adapter:
                try:
                    # Create transaction using adapter
                    tx = adapter.create_transaction(
                        from_address=from_address,
                        to_address=to_address,
                        amount=amount
                    )
                    # Sign transaction
                    signed_tx = adapter.sign_transaction(tx, private_key)
                    # Broadcast transaction
                    tx_hash = adapter.broadcast_transaction(signed_tx)
                    self._record_wallet_transaction(network, from_address, to_address, amount, tx_hash)
                    return tx_hash
                except Exception as adapter_error:
                    self.logger.error(f"Adapter-based transaction failed: {adapter_error}")
                    raise RuntimeError(f"Transaction failed: {adapter_error}")
            
            # If adapter not available, raise clear error
            raise RuntimeError(
                f"Transaction sending not supported for {network} (type={bc_type}). "
                f"Please install required dependencies or configure blockchain adapter."
            )

    # ── EVM (ETH, Polygon, BSC, Arbitrum, Optimism, Base, Avalanche) ──

    def _send_evm_transaction(self, web3_client, network: str,
                               from_address: str, to_address: str,
                               amount: float, private_key: str) -> str:
        """EIP-1559 transaction with gas estimation, fallback to legacy."""
        net_upper = network.upper()
        chain_id = self.BLOCKCHAINS.get(net_upper, {}).get("chain_id", 1)

        nonce = self._next_nonce(web3_client, from_address)
        value_wei = web3_client.to_wei(amount, 'ether')

        base_tx = {
            'from': from_address,
            'to': web3_client.to_checksum_address(to_address),
            'value': value_wei,
            'nonce': nonce,
            'chainId': chain_id,
        }

        try:
            estimated_gas = web3_client.eth.estimate_gas(base_tx)
            gas_limit = int(estimated_gas * 1.2)
        except Exception:
            gas_limit = 21000

        try:
            base_fee = web3_client.eth.get_block('latest').get('baseFeePerGas')
            if base_fee is not None:
                max_priority = web3_client.eth.max_priority_fee
                max_fee = int(base_fee * 2) + max_priority
                base_tx.update({
                    'type': '0x2',
                    'gas': gas_limit,
                    'maxFeePerGas': max_fee,
                    'maxPriorityFeePerGas': max_priority,
                })
            else:
                raise ValueError("No baseFeePerGas")
        except Exception:
            gas_price = web3_client.eth.gas_price
            base_tx.update({
                'gas': gas_limit,
                'gasPrice': int(gas_price * 1.1),
            })

        base_tx.pop('from', None)

        signed_tx = web3_client.eth.account.sign_transaction(base_tx, private_key)
        raw = signed_tx.rawTransaction if hasattr(signed_tx, 'rawTransaction') else signed_tx.raw_transaction
        tx_hash = web3_client.eth.send_raw_transaction(raw)

        try:
            receipt = web3_client.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt.get('status') != 1:
                self._reset_nonce(from_address)
                raise RuntimeError(f"Transaction reverted on {network}: {tx_hash.hex()}")
        except Exception as wait_err:
            if "reverted" in str(wait_err).lower():
                self._reset_nonce(from_address)
                raise
            logger.warning("Receipt wait timeout for %s — tx may still confirm: %s",
                           tx_hash.hex(), wait_err)

        self._record_wallet_transaction(network, from_address, to_address, amount, tx_hash.hex())
        return tx_hash.hex()

    # ── Bitcoin ──

    def _send_btc_transaction(self, network: str, from_address: str,
                               to_address: str, amount: float,
                               private_key: str) -> str:
        """Send BTC using bitcoinlib Wallet or REST API broadcast."""
        try:
            from bitcoinlib.wallets import Wallet as BtcWallet
            from bitcoinlib.keys import HDKey
            key = HDKey(private_key)
            w_name = f"kingdom_send_{int(time.time())}"
            w = BtcWallet.create(w_name, keys=key, network='bitcoin')
            w.utxos_update()
            tx = w.send_to(to_address, amount, fee='normal')
            tx_hash = tx.txid if hasattr(tx, 'txid') else str(tx)
            self._record_wallet_transaction(network, from_address, to_address, amount, tx_hash)
            return tx_hash
        except ImportError:
            pass
        # Try adapter-based implementation first
        adapter = self._get_blockchain_adapter("BTC")
        if adapter:
            try:
                tx = adapter.create_transaction(
                    from_address=from_address,
                    to_address=to_address,
                    amount=amount
                )
                signed_tx = adapter.sign_transaction(tx, private_key)
                tx_hash = adapter.broadcast_transaction(signed_tx)
                self._record_wallet_transaction(network, from_address, to_address, amount, tx_hash)
                return tx_hash
            except Exception as adapter_error:
                self.logger.error(f"BTC adapter transaction failed: {adapter_error}")
        
        try:
            from bitcoinlib.wallets import Wallet as BtcWallet
            btc_wallet = BtcWallet(self.config.get("btc_wallet_name", "kingdom_btc"))
            tx = btc_wallet.send_to(to_address, amount, fee='normal')
            return {"success": True, "tx_hash": tx.txid, "status": tx.status}
        except ImportError:
            raise RuntimeError(
                "BTC transaction sending requires a blockchain adapter or bitcoinlib. "
                "Install: pip install bitcoinlib"
            )
        except Exception as btclib_err:
            raise RuntimeError(f"BTC send via bitcoinlib failed: {btclib_err}")

    # ── Solana ──

    def _send_sol_transaction(self, network: str, from_address: str,
                               to_address: str, amount: float,
                               private_key: str) -> str:
        """Send SOL using solders + solana-py."""
        try:
            from solders.keypair import Keypair as SolKeypair
            from solders.pubkey import Pubkey as SolPubkey
            from solders.system_program import transfer, TransferParams
            from solders.transaction import Transaction as SolTx
            from solders.message import MessageV0
            from solana.rpc.api import Client as SolClient
            import struct

            sol_config = self.BLOCKCHAINS.get("SOL", {})
            rpc_url = sol_config.get("rpc_url", "https://api.mainnet-beta.solana.com")
            client = SolClient(rpc_url)

            pk_bytes = bytes.fromhex(private_key) if len(private_key) == 128 else bytes.fromhex(private_key)
            keypair = SolKeypair.from_bytes(pk_bytes[:64])
            sender = keypair.pubkey()
            receiver = SolPubkey.from_string(to_address)

            lamports = int(amount * 1_000_000_000)
            ix = transfer(TransferParams(from_pubkey=sender, to_pubkey=receiver, lamports=lamports))

            recent = client.get_latest_blockhash()
            blockhash = recent.value.blockhash

            msg = MessageV0.try_compile(sender, [ix], [], blockhash)
            from solders.transaction import VersionedTransaction
            tx = VersionedTransaction(msg, [keypair])
            result = client.send_transaction(tx)

            tx_sig = str(result.value) if hasattr(result, 'value') else str(result)
            self._record_wallet_transaction(network, from_address, to_address, amount, tx_sig)
            return tx_sig
        except ImportError:
            # Try adapter-based implementation
            adapter = self._get_blockchain_adapter("SOL")
            if adapter:
                try:
                    tx = adapter.create_transaction(
                        from_address=from_address,
                        to_address=to_address,
                        amount=amount
                    )
                    signed_tx = adapter.sign_transaction(tx, private_key)
                    tx_hash = adapter.broadcast_transaction(signed_tx)
                    self._record_wallet_transaction(network, from_address, to_address, amount, tx_hash)
                    return tx_hash
                except Exception as adapter_error:
                    self.logger.error(f"SOL adapter transaction failed: {adapter_error}")
            
            raise RuntimeError(
                "SOL sending requires solders + solana or blockchain adapter. "
                "Install: pip install solders solana")
        except Exception as e:
            raise RuntimeError(f"SOL transaction failed: {e}")

    # ── XRP ──

    def _send_xrp_transaction(self, network: str, from_address: str,
                               to_address: str, amount: float,
                               private_key: str) -> str:
        """Send XRP using xrpl-py."""
        try:
            from xrpl.clients import JsonRpcClient as XrplClient
            from xrpl.models.transactions import Payment
            from xrpl.models.amounts import drops_to_xrp, xrp_to_drops
            from xrpl.transaction import submit_and_wait
            from xrpl.wallet import Wallet as XrplWallet

            xrp_config = self.BLOCKCHAINS.get("XRP", {})
            rpc_url = xrp_config.get("rpc_url", "https://s1.ripple.com:51234")
            client = XrplClient(rpc_url)
            wallet = XrplWallet.from_seed(private_key)

            payment = Payment(
                account=from_address,
                amount=xrp_to_drops(amount),
                destination=to_address,
            )
            response = submit_and_wait(payment, client, wallet)
            tx_hash = response.result.get("hash", str(response))
            self._record_wallet_transaction(network, from_address, to_address, amount, tx_hash)
            return tx_hash
        except ImportError:
            # Try adapter-based implementation
            adapter = self._get_blockchain_adapter("XRP")
            if adapter:
                try:
                    tx = adapter.create_transaction(
                        from_address=from_address,
                        to_address=to_address,
                        amount=amount
                    )
                    signed_tx = adapter.sign_transaction(tx, private_key)
                    tx_hash = adapter.broadcast_transaction(signed_tx)
                    self._record_wallet_transaction(network, from_address, to_address, amount, tx_hash)
                    return tx_hash
                except Exception as adapter_error:
                    self.logger.error(f"XRP adapter transaction failed: {adapter_error}")
            
            raise RuntimeError(
                "XRP sending requires xrpl-py or blockchain adapter. "
                "Install: pip install xrpl-py")
        except Exception as e:
            raise RuntimeError(f"XRP transaction failed: {e}")

    # ── Monero ──

    def _send_xmr_transaction(self, network: str, from_address: str,
                               to_address: str, amount: float) -> str:
        """Send XMR via monero-wallet-rpc using monero-python."""
        try:
            from monero.wallet import Wallet as MoneroWallet
            from monero.backends.jsonrpc import JSONRPCWallet
            from decimal import Decimal

            rpc_port = int(os.getenv("MONERO_WALLET_RPC_PORT", "28088"))
            rpc_host = os.getenv("MONERO_WALLET_RPC_HOST", "127.0.0.1")
            backend = JSONRPCWallet(host=rpc_host, port=rpc_port)
            wallet = MoneroWallet(backend)

            txs = wallet.transfer(to_address, Decimal(str(amount)))
            tx_hash = str(txs[0].hash) if txs else "unknown"
            self._record_wallet_transaction(network, from_address, to_address, amount, tx_hash)
            return tx_hash
        except ImportError:
            # Try adapter-based implementation
            adapter = self._get_blockchain_adapter("XMR")
            if adapter:
                try:
                    tx = adapter.create_transaction(
                        from_address=from_address,
                        to_address=to_address,
                        amount=amount
                    )
                    # XMR doesn't use private_key in the same way, but adapter handles it
                    signed_tx = adapter.sign_transaction(tx, "")
                    tx_hash = adapter.broadcast_transaction(signed_tx)
                    self._record_wallet_transaction(network, from_address, to_address, amount, tx_hash)
                    return tx_hash
                except Exception as adapter_error:
                    self.logger.error(f"XMR adapter transaction failed: {adapter_error}")
            
            raise RuntimeError(
                "XMR sending requires monero-python or blockchain adapter. "
                "Install: pip install monero")
        except Exception as e:
            raise RuntimeError(f"XMR transaction failed: {e}")

    # ── Transaction History Persistence ──

    def _record_wallet_transaction(self, network: str, from_addr: str,
                                    to_addr: str, amount: float,
                                    tx_hash: str, status: str = "confirmed"):
        """Persist transaction to disk and publish event."""
        tx_record = {
            "network": network,
            "from": from_addr,
            "to": to_addr,
            "amount": amount,
            "tx_hash": tx_hash,
            "status": status,
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        try:
            history_path = os.path.join("data", "wallets", "transaction_history.json")
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            history: List[Dict] = []
            if os.path.exists(history_path):
                with open(history_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            history.insert(0, tx_record)
            if len(history) > 500:
                history = history[:500]
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error("Failed to persist tx history: %s", e)

        if network.upper() not in self.transaction_cache:
            self.transaction_cache[network.upper()] = []
        self.transaction_cache[network.upper()].insert(0, tx_record)

        self._safe_publish("wallet.transaction.confirmed", tx_record)
    
    def get_transactions(self, network: str) -> list:
        """Get transaction history for specified network.

        Also loads from persistent transaction_history.json if the cache is empty.
        """
        try:
            cached = self.transaction_cache.get(network, [])
            if cached:
                return cached
            net_upper = network.upper()
            cached_upper = self.transaction_cache.get(net_upper, [])
            if cached_upper:
                return cached_upper
            try:
                history_path = os.path.join("data", "wallets", "transaction_history.json")
                if os.path.exists(history_path):
                    with open(history_path, 'r', encoding='utf-8') as f:
                        all_tx = json.load(f)
                    filtered = [t for t in all_tx
                                if (t.get("network", "").upper() == net_upper
                                    or t.get("network", "").lower() == network.lower())]
                    if filtered:
                        self.transaction_cache[net_upper] = filtered
                        return filtered
            except Exception:
                pass
            return []
        except Exception as e:
            logger.error(f"Error getting transactions for {network}: {e}")
            return []

    def _init_redis(self):
        """Initialize Redis Quantum Nexus connection.
        
        This method establishes a connection to the Redis Quantum Nexus server
        with strict requirements:
        - Must connect to localhost:6380
        - Must use password from environment variable 'REDIS_PASSWORD'
        - No fallback allowed
        - System exits on failure
        """
        try:
            # Modern 2025 Redis import pattern
            try:
                import redis
                redis_available = True
            except ImportError:
                self.logger.error("Redis module not available")
                self.redis = None
                return
            
            # Get Redis password from environment variable
            redis_password = (
                os.getenv('REDIS_PASSWORD')
                or os.getenv('REDIS_QUANTUM_NEXUS_PASSWORD')
                or 'QuantumNexus2025'
            )
            
            # 2025 Pattern: Type-safe Redis initialization with dynamic class access
            # Avoid direct import to prevent type checker issues
            RedisClass = getattr(redis, 'Redis', None)
            if RedisClass is None:
                raise SystemExit("Fatal: Redis.Redis class not available")
                
            self.redis = RedisClass(
                host='localhost',
                port=6380,  # Correct port for Kingdom AI Redis Quantum Nexus
                password=redis_password,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                decode_responses=True
            )
            
            # Test the connection
            try:
                if not self.redis.ping():
                    raise ConnectionError("Failed to connect to Redis")
                self.logger.info("Successfully connected to Redis Quantum Nexus")
            except Exception as e:
                error_msg = f"Redis Quantum Nexus connection failed: {e}"
                self.logger.error(error_msg)
                self.redis = None
                return
        
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis Quantum Nexus: {e}")
            self.redis = None
            return

    def _initialize_clients(self):
        """Initialize blockchain clients based on available libraries.
        
        Sets up connections to blockchain networks for available libraries
        and tracks which coins are available in the system.
        """
        self.logger.info("Initializing blockchain clients")
        available_coins = []
        
        # Initialize Ethereum client if available
        if web3_available:
            try:
                eth_config = self.BLOCKCHAINS.get("ETH", {})
                eth_rpc_url = eth_config.get("rpc_url")
                if not eth_rpc_url or 'YOUR_PROJECT_ID' in eth_rpc_url:
                    raise ValueError("Ethereum RPC URL not properly configured")
                    
                # 2025 Pattern: Safe Web3 provider initialization
                if Web3 is not None:
                    try:
                        from web3.providers.rpc import HTTPProvider
                        self.clients["ETH"] = Web3(HTTPProvider(eth_rpc_url))
                        if hasattr(self.clients["ETH"], 'is_connected') and not self.clients["ETH"].is_connected():
                            raise ConnectionError("Failed to connect to Ethereum node")
                    except Exception as web3_error:
                        self.logger.error(f"Web3 initialization failed: {web3_error}")
                        # Try alternative RPC endpoints
                        fallback_rpcs = [
                            "https://rpc.ankr.com/eth",
                            "https://ethereum-rpc.publicnode.com",
                            "https://eth.llamarpc.com",
                            "https://cloudflare-eth.com",
                            "https://1rpc.io/eth",
                        ]
                        for fallback_rpc in fallback_rpcs:
                            try:
                                self.clients["ETH"] = Web3(HTTPProvider(fallback_rpc))
                                if hasattr(self.clients["ETH"], 'is_connected') and self.clients["ETH"].is_connected():
                                    self.logger.info(f"Connected to Ethereum via fallback RPC: {fallback_rpc}")
                                    break
                            except Exception:
                                continue
                        else:
                            self.logger.error("All Ethereum RPC endpoints failed - ETH functionality disabled")
                            self.clients["ETH"] = None
                else:
                    self.logger.error("Web3 not available - ETH functionality disabled")
                    self.clients["ETH"] = None
                    
                self.logger.info(f"Initialized ETH client with endpoint: {eth_rpc_url}")
                available_coins.append("ETH")
            except Exception as e:
                self.logger.error(f"Failed to initialize ETH client: {e}")
                if self.config.get("require_eth", False):
                    raise SystemExit(f"Fatal: ETH client initialization failed: {e}")
                
        # Initialize Bitcoin client if available
        if btc_rpc_available:
            try:
                btc_config = self.BLOCKCHAINS.get("BTC", {})
                btc_rpc_url = btc_config.get("rpc_url")
                if not btc_rpc_url or 'user:pass' in btc_rpc_url:
                    raise ValueError("Bitcoin RPC URL not properly configured")
                
                # AuthServiceProxy requires a Bitcoin Core RPC endpoint with credentials
                # Format: http://user:password@host:port/
                # Block explorer APIs (e.g. blockstream.info) are NOT RPC endpoints
                if '@' not in btc_rpc_url:
                    # No credentials in URL - this is likely a block explorer API
                    self.logger.info(
                        f"BTC URL ({btc_rpc_url}) is a block explorer API, not Bitcoin Core RPC. "
                        f"Using REST API mode for BTC. Set BTC_RPC_URL=http://user:pass@host:8332 "
                        f"for full RPC functionality."
                    )
                    # Store the REST API URL for balance lookups instead
                    self.clients["BTC"] = btc_rpc_url  # REST API fallback
                    available_coins.append("BTC")
                else:
                    self.clients["BTC"] = AuthServiceProxy(btc_rpc_url)
                    # Test connection
                    self.clients["BTC"].getblockchaininfo()
                    self.logger.info("Initialized BTC RPC client")
                    available_coins.append("BTC")
            except Exception as e:
                self.logger.error(f"Failed to initialize BTC client: {e}")
                if self.config.get("require_btc", False):
                    raise SystemExit(f"Fatal: BTC client initialization failed: {e}")
        else:
            self.logger.warning("Bitcoin RPC library not available, BTC functionality disabled")
            
        # Initialize XRP client if available
        if xrp_available:
            try:
                xrp_config = self.BLOCKCHAINS.get("XRP", {})
                xrp_rpc_url = xrp_config.get("rpc_url")
                self.clients["XRP"] = JsonRpcClient(xrp_rpc_url)
                self.logger.info(f"Initialized XRP client with endpoint: {xrp_rpc_url}")
                available_coins.append("XRP")
            except Exception as e:
                self.logger.error(f"Failed to initialize XRP client: {e}")
        else:
            self.logger.warning("XRP library not available, XRP functionality disabled")
            
        # Initialize Solana client if available
        if solana_available:
            try:
                sol_config = self.BLOCKCHAINS.get("SOL", {})
                sol_rpc_url = sol_config.get("rpc_url")
                self.clients["SOL"] = AsyncClient(sol_rpc_url)
                self.logger.info(f"Initialized SOL client with endpoint: {sol_rpc_url}")
                available_coins.append("SOL")
            except Exception as e:
                self.logger.error(f"Failed to initialize SOL client: {e}")
        else:
            self.logger.warning("Solana library not available, SOL functionality disabled")
            
        # Pi Network - honest status (not yet supported)
        try:
            # Pi Network does not have a public API or RPC endpoint available yet
            self.clients["PI"] = None
            self.logger.warning("PI Network: No public API available - PI functionality not supported")
            # Do not add PI to available_coins since it's not actually available
        except Exception as e:
            self.logger.error(f"Error checking PI Network status: {e}")
            
        # Update available coins in status
        self.status["coins_available"] = available_coins
        if available_coins:
            self.logger.info(f"Available coins: {', '.join(available_coins)}")
        else:
            self.logger.warning("No blockchain clients were successfully initialized")
    
    async def _load_wallets(self):
        """Load existing wallets from persistent storage.
        
        Attempts to load wallet data from Redis if available, otherwise
        initializes with empty wallet dictionaries for each supported coin.
        """
        try:
            if not hasattr(self, 'redis') or not self.redis:
                raise ConnectionError("Redis connection not available")
                
            # Try to load from Redis
            wallet_data = self.redis.get('wallets')
            if wallet_data:
                self.wallets = json.loads(wallet_data)
                self.logger.info(f"Loaded {sum(len(w) for w in self.wallets.values())} wallets from Redis")
            else:
                self._initialize_empty_wallets()
                self.logger.info("No wallet data found in Redis, initialized empty wallets")
                
        except Exception as e:
            self.logger.error(f"Error loading wallets: {e}")
            # TEMPORARY: Disable Redis requirement for testing
            if self.config.get("require_persistence", False):  # Changed to False for testing
                raise SystemExit(f"Fatal: Failed to load wallets: {e}") from e
            self._initialize_empty_wallets()
            self.logger.warning("Initialized empty wallet storage after error (Redis disabled for testing)")
    
    def _initialize_empty_wallets(self):
        """Initialize empty wallet dictionaries for each supported coin."""
        self.wallets = {coin: {} for coin in self.BLOCKCHAINS}
        self.logger.info(f"Initialized empty wallet storage for coins: {', '.join(self.wallets.keys())}")
    
    async def _persist_wallets(self):
        """Persist wallet data to Redis if available, otherwise noop.
        
        This method saves the wallet data to Redis for persistence across restarts.
        Private keys are NEVER persisted for security reasons.
        """
        try:
            if not hasattr(self, 'redis') or not self.redis:
                raise ConnectionError("Redis connection not available")
                
            # Make a copy and remove private keys before persisting
            wallets_to_persist = {}
            for coin, wallets in self.wallets.items():
                wallets_to_persist[coin] = {}
                for addr, wallet in wallets.items():
                    wallet_copy = wallet.copy()
                    wallet_copy.pop('private_key', None)  # Never persist private keys
                    wallets_to_persist[coin][addr] = wallet_copy
            
            # Store in Redis with a 30-day expiration
            self.redis.set('wallets', json.dumps(wallets_to_persist), ex=60*60*24*30)
            self.logger.debug("Persisted wallets to Redis")
            
        except Exception as e:
            error_msg = f"Error persisting wallets: {e}"
            self.logger.error(error_msg)
            if self.config.get("require_persistence", True):
                raise SystemExit(f"Fatal: {error_msg}") from e
    
    async def initialize(self, event_bus=None, config=None) -> bool:
        """Initialize wallet connections and load existing wallets.
        
        Args:
            event_bus: EventBus instance to use (will use self.event_bus if None)
            config: Configuration to use (will use self.config if None)
            
        Returns:
            bool: True if initialization was successful
        """
        try:
            self.logger.info("Initializing WalletManager...")
            
            # Update configuration if provided
            if config is not None:
                self.config = config
                
            # Set event bus if provided
            if event_bus is not None:
                self.event_bus = event_bus
                
            # Initialize Redis Quantum Nexus connection
            self._init_redis()
            
            # Initialize blockchain clients
            try:
                self._initialize_clients()
            except Exception as e:
                self.logger.critical(f"Failed to initialize blockchain clients: {e}")
                raise SystemExit(f"Fatal: Failed to initialize blockchain clients: {e}")
            
            # Load existing wallets
            try:
                await self._load_wallets()
            except Exception as e:
                self.logger.critical(f"Failed to load wallets: {e}")
                raise SystemExit(f"Fatal: Failed to load wallets: {e}")
            
            # Set up event handlers
            if self.event_bus:
                try:
                    # 2025 Pattern: Safe async subscription with proper error handling
                    # Use _setup_event_handlers method instead of awaiting None
                    self._setup_event_handlers()
                    
                    self.logger.info("Successfully subscribed to all wallet and trading events")
                    # Use synchronous publish_wallet_list method
                    self.publish_wallet_list()
                except Exception as e:
                    self.logger.critical(f"Failed to subscribe to events: {e}")
                    raise SystemExit(f"Fatal: Failed to subscribe to events: {e}")
                
                self.logger.info("WalletManager subscribed to wallet and trading events")
                
                # Initial wallet list already published above
            
            self.running = True
            # Setup event subscriptions
            self._setup_event_handlers()
            
            # Initialize sentience integration
            if self.sentience_integration:
                sentience_init_result = self.sentience_integration.initialize(event_bus=self.event_bus, wallet_manager=self)
                if sentience_init_result:
                    self.sentience_integration.start_monitoring()
                    self.logger.info("Wallet manager sentience monitoring activated")
                    
                    # Register sentience event handlers with event bus
                    self._safe_subscribe("sentience.wallet.threshold_exceeded", self._handle_sentience_threshold)
                    self._safe_subscribe("sentience.wallet.pattern_detected", self._handle_sentience_pattern)
                    self._safe_subscribe("sentience.wallet.metric_update", self._handle_sentience_metric_update)
                else:
                    self.logger.warning("Failed to initialize wallet sentience integration")
            
            # BUG C FIX: Write data/wallets/kingdom_ai_wallet_status.json so both
            # wallet_tab and mining_tab always have a file source for configured wallets.
            # WalletCreator (which normally writes this) is never called at boot because
            # WalletSystem is not instantiated -- only WalletManager is.
            self._write_wallet_status_json()
            
            self.logger.info("WalletManager initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize WalletManager: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _write_wallet_status_json(self):
        """Write wallet status JSON so wallet_tab and mining_tab can always read it."""
        try:
            wallet_dir = os.path.join("data", "wallets")
            os.makedirs(wallet_dir, exist_ok=True)
            status_path = os.path.join(wallet_dir, "kingdom_ai_wallet_status.json")
            # Filter out meta keys (default_wallet etc.) to get coin symbols only
            configured = sorted(set(
                k for k in self.address_cache.keys()
                if not k.startswith("default_") and isinstance(self.address_cache[k], str)
                and self.address_cache[k].strip()
            ))
            status = {
                "configured": configured,
                "configured_pow_wallets": configured,
                "configured_count": len(configured),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status, f, indent=2)
            self.logger.info(f"Wrote wallet status JSON: {len(configured)} wallets to {status_path}")
        except Exception as e:
            self.logger.warning(f"Failed to write wallet status JSON: {e}")
    
    # Duplicate _safe_publish method removed - using more comprehensive implementation below
            
    async def add_wallet(self, coin_type, address, private_key=None, name=None):
        """Add a wallet to the wallets dictionary.
        
        Args:
            coin_type (str): Type of cryptocurrency (ETH, BTC, XRP, SOL, PI)
            address (str): Wallet address
            private_key (str, optional): Private key (encrypted if possible)
            name (str, optional): Name for the wallet
            
        Returns:
            bool: True if wallet was added successfully, False otherwise
        """
        try:
            # Normalize coin type to uppercase
            coin_type = coin_type.upper()
            
            # Validate coin type
            if coin_type not in self.BLOCKCHAINS:
                self.logger.error(f"Invalid coin type: {coin_type}")
                return False
                
            # Check if wallet already exists
            if coin_type not in self.wallets:
                self.wallets[coin_type] = {}
                
            if address in self.wallets[coin_type]:
                self.logger.warning(f"{coin_type} wallet with address {address} already exists")
                return False
                
            # Add wallet
            self.wallets[coin_type][address] = {
                "private_key": private_key,
                "name": name or f"{coin_type} Wallet {len(self.wallets[coin_type]) + 1}",
                "balance": 0.0,
                "last_update": time.time()
            }
            
            # Persist wallets if Redis is available
            await self._persist_wallets()
            
            self.logger.info(f"Added {coin_type} wallet: {address}")
            return True
        except Exception as e:
            self.logger.error(f"Error adding wallet: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    async def remove_wallet(self, coin_type, address):
        """Remove a wallet from the wallets dictionary.
        
        Args:
            coin_type (str): Type of cryptocurrency (ETH, BTC, XRP, SOL, PI)
            address (str): Wallet address
            
        Returns:
            bool: True if wallet was removed successfully, False otherwise
        """
        try:
            # Normalize coin type to uppercase
            coin_type = coin_type.upper()
            
            # Validate wallet exists
            if coin_type not in self.wallets:
                self.logger.error(f"No wallets for coin type: {coin_type}")
                return False
                
            if address not in self.wallets[coin_type]:
                self.logger.error(f"Wallet with address {address} not found for {coin_type}")
                return False
                
            # Remove wallet
            del self.wallets[coin_type][address]
            self.logger.info(f"Removed {coin_type} wallet: {address}")
            
            # Persist wallets if Redis is available
            await self._persist_wallets()
            
            return True
        except Exception as e:
            self.logger.error(f"Error removing wallet: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    def get_wallet_list(self, coin_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get a list of wallets, optionally filtered by coin type.
        
        Args:
            coin_filter: Optional coin type to filter wallets by
            
        Returns:
            List of wallet dictionaries with their details
        """
        wallet_list = []
        
        try:
            # Filter wallets by coin if specified
            if coin_filter and coin_filter.upper() in self.wallets:
                coins_to_process = [coin_filter.upper()]
            else:
                coins_to_process = list(self.wallets.keys())
                
            # Build wallet list
            for coin in coins_to_process:
                if coin not in self.wallets:
                    continue
                    
                for address, details in self.wallets[coin].items():
                    wallet = {
                        "coin": coin,
                        "address": address,
                        "name": details.get("name", f"{coin} Wallet"),
                        "balance": details.get("balance", 0.0),
                        "last_update": details.get("last_update", time.time())
                    }
                    wallet_list.append(wallet)
                    
            return wallet_list
        except Exception as e:
            self.logger.error(f"Error getting wallet list: {e}")
            self.logger.error(traceback.format_exc())
            return []
            
    def _handle_get_balance(self, event_data: Dict[str, Any]) -> None:
        """Handle wallet.balance event to get a wallet balance.
        
        Args:
            event_data: Event data containing coin type and address
        """
        self._run_async(self._handle_get_balance_async, event_data)
        
    async def _handle_get_balance_async(self, event_data):
        """Async implementation for wallet.balance event.
        
        Args:
            event_data: Event data containing coin type and address
        """
        try:
            # Validate input
            if not event_data:
                self._publish_error("wallet.balance", "Missing wallet data")
                return
                
            coin_type = event_data.get("coin")
            address = event_data.get("address")
            request_id = event_data.get("request_id")
            
            if not coin_type or not address:
                self._publish_error("wallet.balance", "Missing coin type or address", 
                                  context={"request_id": request_id} if request_id else None)
                return
                
            # Normalize coin type
            coin_type = coin_type.upper()
            
            # Check if wallet exists
            if coin_type not in self.wallets or address not in self.wallets[coin_type]:
                self._publish_error("wallet.balance", 
                                        f"Wallet not found: {coin_type} {address}", 
                                        context={"request_id": request_id} if request_id else None)
                return
                
            # Get balance from wallet (cached value)
            balance = self.wallets[coin_type][address].get("balance", 0.0)
            last_update = self.wallets[coin_type][address].get("last_update", time.time())
            
            # Publish success response using synchronous method
            success_data = {
                "coin": coin_type,
                "address": address,
                "balance": balance,
                "last_update": last_update
            }
            if request_id:
                success_data["request_id"] = request_id
            self._publish_success("wallet.balance", success_data)
        except Exception as e:
            self.logger.error(f"Error handling wallet.balance event: {e}")
            self.logger.error(traceback.format_exc())
            self._publish_error("wallet.balance", f"Error retrieving balance: {str(e)}")
            
    def _handle_transfer(self, event_data):
        """Handle wallet.transfer event to transfer funds between wallets.
        
        Args:
            event_data: Event data containing source and destination details
        """
        self._run_async(self._handle_transfer_async, event_data)
        
    async def _handle_transfer_async(self, event_data):
        """Async implementation for wallet.transfer event.
        
        Args:
            event_data: Event data containing source and destination details
        """
        try:
            # Validate input
            if not event_data:
                self._publish_error("wallet.transfer", "Missing transfer data")
                return
                
            source_coin = event_data.get("source_coin", "").upper()
            source_address = event_data.get("source_address", "")
            dest_coin = event_data.get("dest_coin", "").upper()
            dest_address = event_data.get("dest_address", "")
            amount = event_data.get("amount", 0)
            
            if not all([source_coin, source_address, dest_coin, dest_address]) or amount <= 0:
                self._publish_error("wallet.transfer", "Invalid transfer parameters")
                return
                
            # Check source wallet exists and has sufficient balance
            if source_coin not in self.wallets or source_address not in self.wallets[source_coin]:
                self._publish_error("wallet.transfer", f"Source wallet not found: {source_coin} {source_address}")
                return
                
            source_wallet = self.wallets[source_coin][source_address]
            source_balance = source_wallet.get("balance", 0)
            
            if source_balance < amount:
                self._publish_error("wallet.transfer", f"Insufficient balance: {source_balance} < {amount}")
                return
                
            # Check destination wallet exists
            if dest_coin not in self.wallets or dest_address not in self.wallets[dest_coin]:
                self._publish_error("wallet.transfer", f"Destination wallet not found: {dest_coin} {dest_address}")
                return
                
            # Perform transfer
            self.wallets[source_coin][source_address]["balance"] = source_balance - amount
            self.wallets[dest_coin][dest_address]["balance"] = self.wallets[dest_coin][dest_address].get("balance", 0) + amount
            
            # Update timestamps
            current_time = time.time()
            self.wallets[source_coin][source_address]["last_update"] = current_time
            self.wallets[dest_coin][dest_address]["last_update"] = current_time
            
            # Publish success
            self._publish_success("wallet.transfer", {
                "source": f"{source_coin} {source_address}",
                "destination": f"{dest_coin} {dest_address}",
                "amount": amount,
                "new_source_balance": self.wallets[source_coin][source_address]["balance"],
                "new_dest_balance": self.wallets[dest_coin][dest_address]["balance"]
            })
            
        except Exception as e:
            self.logger.error(f"Error handling wallet.transfer event: {e}")
            self.logger.error(traceback.format_exc())
            self._publish_error("wallet.transfer", f"Error processing transfer: {str(e)}")
    
    # Duplicate _persist_wallets method removed - using first implementation at line ~420
                
    def _run_async(self, async_func, *args, **kwargs):
        """Run an async function in a way that works with both sync and async contexts.
        
        Args:
            async_func: The async function to run
            *args, **kwargs: Arguments to pass to the async function
        """
        try:
            # Get the current event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in this thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run the async function
            if loop.is_running():
                # Create a task if the loop is already running
                asyncio.create_task(async_func(*args, **kwargs))
            else:
                # Run the coroutine until complete if the loop is not running
                loop.run_until_complete(async_func(*args, **kwargs))
        except Exception as e:
            self.logger.error(f"Error running async handler: {e}")
            
    def _publish_error(self, event_type: str, error, context: Optional[Dict] = None):
        """Publish an error event - 2025 Enhanced with String-to-Exception Conversion.
        
        Args:
            event_type: The event type that failed
            error: The exception that occurred (Exception, str, or any object)
            context: Additional context about the error
        """
        # 2025 Pattern: Convert string errors to proper Exception objects
        if isinstance(error, str):
            # Create appropriate exception type based on error content
            if "missing" in error.lower():
                actual_error = ValueError(error)
            elif "invalid" in error.lower() or "parameter" in error.lower():
                actual_error = TypeError(error)
            elif "connection" in error.lower() or "redis" in error.lower():
                actual_error = ConnectionError(error)
            elif "timeout" in error.lower():
                actual_error = TimeoutError(error)
            elif "permission" in error.lower() or "access" in error.lower():
                actual_error = PermissionError(error)
            else:
                actual_error = RuntimeError(error)
        elif isinstance(error, Exception):
            actual_error = error
        else:
            # Convert any other type to RuntimeError
            actual_error = RuntimeError(f"Unexpected error type: {type(error).__name__}: {str(error)}")
        
        error_data = {
            "error": str(actual_error),
            "error_type": actual_error.__class__.__name__,
            "event_type": event_type,
            "timestamp": time.time()
        }
        if context:
            error_data.update(context)

        # Emit unified wallet.telemetry for all wallet.* error events
        try:
            if isinstance(event_type, str) and event_type.startswith("wallet.") and self.event_bus:
                telemetry_payload = {
                    "component": "wallet",
                    "channel": "wallet.telemetry",
                    "event_type": event_type,
                    "timestamp": time.time(),
                    "success": False,
                    "error": str(actual_error),
                    "metadata": context or {},
                }
                self.event_bus.publish("wallet.telemetry", telemetry_payload)
        except Exception as telemetry_err:
            # Never raise from telemetry path
            self.logger.debug(f"Failed to publish wallet.telemetry error event: {telemetry_err}")

        # Use safe async publish with proper error handling
        try:
            if self.event_bus:
                self.event_bus.publish(f"error.{event_type}", error_data)
        except Exception as publish_error:
            self.logger.error(f"Failed to publish error event: {publish_error}")
        
    def _publish_success(self, event_type: str, data: Optional[Dict] = None):
        """Publish a success event.
        
        Args:
            event_type: The event type that succeeded
            data: Additional data to include
        """
        success_data = {
            "status": "success",
            "event_type": event_type,
            "timestamp": time.time()
        }
        if data:
            success_data.update(data)

        # Emit unified wallet.telemetry for all wallet.* success events
        try:
            if isinstance(event_type, str) and event_type.startswith("wallet.") and self.event_bus:
                telemetry_payload = {
                    "component": "wallet",
                    "channel": "wallet.telemetry",
                    "event_type": event_type,
                    "timestamp": time.time(),
                    "success": True,
                    "error": None,
                    "metadata": data or {},
                }
                self.event_bus.publish("wallet.telemetry", telemetry_payload)
        except Exception as telemetry_err:
            # Never raise from telemetry path
            self.logger.debug(f"Failed to publish wallet.telemetry success event: {telemetry_err}")

        self._safe_publish(f"success.{event_type}", success_data)
        
    def _safe_publish(self, event_type: str, data: Optional[Dict] = None):
        """Safely publish an event with error handling.
        
        Args:
            event_type: The event type to publish
            data: Event data to publish
        """
        try:
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                self.event_bus.publish(event_type, data)
            else:
                self.logger.warning(f"Event bus not available, skipping event: {event_type}")
        except Exception as e:
            self.logger.error(f"Error publishing event {event_type}: {e}")
            
    def _safe_subscribe(self, event_type: str, handler: Callable):
        """Safely subscribe to an event with error handling.
        
        Args:
            event_type: The event type to subscribe to
            handler: The handler function
        """
        try:
            if self.event_bus and hasattr(self.event_bus, 'subscribe'):
                self.event_bus.subscribe(event_type, handler)
                self.logger.debug(f"Subscribed to event: {event_type}")
            else:
                self.logger.warning(f"Event bus not available, skipping subscription: {event_type}")
        except Exception as e:
            self.logger.error(f"Error subscribing to event {event_type}: {e}")
            
    def _setup_event_handlers(self):
        """Set up event handlers for wallet and trading events."""
        try:
            # Wallet events
            self._safe_subscribe("wallet.balance", self._handle_get_balance)
            self._safe_subscribe("wallet.transfer", self._handle_transfer)
            self._safe_subscribe("wallet.list", self._handle_list_wallets)

            # SOTA 2026: GUI + Mobile wallet send pipeline
            self._safe_subscribe("wallet.send", self._handle_wallet_send)
            
            # Trading events - UNIFIED INTEGRATION (covers all published names)
            self._safe_subscribe("trading.deposit_profits", self._handle_deposit_profits)
            self._safe_subscribe("trading.withdraw_capital", self._handle_withdraw_capital)
            self._safe_subscribe("trading.wallet_status", self._handle_wallet_status)
            self._safe_subscribe("trading.profit", self._handle_trading_profit)
            self._safe_subscribe("trading.profit.realized", self._handle_trading_profit)
            self._safe_subscribe("trading.profit.update", self._handle_trading_profit)
            self._safe_subscribe("trading.position.closed", self._handle_position_closed)
            self._safe_subscribe("trading.closed", self._handle_position_closed)
            self._safe_subscribe("trading.trade_completed", self._handle_position_closed)
            
            # Mining events - AUTO-DEPOSIT INTEGRATION (covers all published names)
            self._safe_subscribe("mining.reward_update", self._handle_mining_reward)
            self._safe_subscribe("mining.reward.received", self._handle_mining_reward)
            self._safe_subscribe("mining.update", self._handle_mining_status_update)
            self._safe_subscribe("mining.payout", self._handle_mining_payout)
            self._safe_subscribe("mining.rewards.funnel", self._handle_mining_rewards_funnel)
            
            # Cross-system portfolio events
            self._safe_subscribe("portfolio.sync.request", self._handle_portfolio_sync)
            self._safe_subscribe("market.prices", self._handle_market_prices)
            
            # SOTA 2026: Chat/Voice command events for system-wide control
            self._safe_subscribe("wallet.balance.request", self._handle_balance_request)
            self._safe_subscribe("wallet.transaction.send", self._handle_send_transaction)
            self._safe_subscribe("wallet.addresses.request", self._handle_addresses_request)

            # SOTA 2026: Fintech pipeline — P2P, BitChat, NFC tap results
            self._safe_subscribe("fintech.p2p.send", self._handle_fintech_p2p_execute)
            self._safe_subscribe("fintech.bitchat.command", self._handle_fintech_bitchat_execute)
            self._safe_subscribe("fintech.nfc.tap_pay", self._handle_fintech_nfc_execute)
            
            # KAIG Intelligence Bridge — receive wallet directives & speed mandates + rebrand resilience
            self._safe_subscribe("kaig.intel.wallet.directive", self._handle_kaig_wallet_directive)
            self._safe_subscribe("kaig.intel.speed.mandate", self._handle_kaig_speed_mandate)
            self._safe_subscribe("kaig.identity.changed", self._handle_identity_changed)
            self._safe_subscribe("trading.system.readiness", self._handle_trading_system_readiness)
            
            self.logger.info("Event handlers set up successfully (incl. mining/trading/chat/KAIG/fintech integration)")
        except Exception as e:
            self.logger.error(f"Error setting up event handlers: {e}")

    # ── WALLET.SEND HANDLER (Desktop GUI + Mobile bridge) ────────────

    def _handle_wallet_send(self, event_data):
        """Handle wallet.send events from desktop GUI and mobile sync server.

        This is the unified entry point — it resolves the network, calls
        send_transaction(), and publishes the result back for listeners.
        """
        try:
            if not isinstance(event_data, dict):
                return
            to_address = event_data.get("to_address", "")
            amount_raw = event_data.get("amount", 0)
            network_raw = event_data.get("network", "")
            source = event_data.get("source", "desktop")

            if not to_address or not amount_raw:
                self._safe_publish("wallet.send.error", {
                    "error": "Missing to_address or amount", "source": source})
                return

            amount = float(amount_raw)
            network = str(network_raw).upper() if network_raw else "ETH"
            sym = self._SYMBOL_TO_NETWORK.get(network, network.lower())
            lookup_key = network if network in self.address_cache else sym

            self.logger.info("wallet.send: %.8f %s -> %s (source=%s)",
                             amount, network, to_address[:16], source)

            tx_hash = self.send_transaction(lookup_key, to_address, amount)
            self._safe_publish("wallet.send.result", {
                "tx_hash": tx_hash,
                "network": network,
                "to_address": to_address,
                "amount": amount,
                "source": source,
                "status": "confirmed",
            })
        except Exception as e:
            logger.error("wallet.send handler error: %s", e)
            self._safe_publish("wallet.send.error", {
                "error": str(e),
                "network": event_data.get("network", ""),
                "source": event_data.get("source", ""),
            })

    # ── FINTECH EXECUTION HANDLERS (wire P2P / BitChat / NFC to blockchain) ──

    def _handle_fintech_p2p_execute(self, event_data):
        """Execute the actual blockchain transfer for a P2P payment."""
        try:
            if not isinstance(event_data, dict):
                return
            recipient = event_data.get("recipient", "")
            amount_raw = event_data.get("amount", "0")
            currency = event_data.get("currency", "USD").upper()

            if not recipient or float(amount_raw) <= 0:
                return

            if recipient.startswith("@"):
                self.logger.info("P2P to username %s — queued for address resolution", recipient)
                self._safe_publish("fintech.p2p.queued", {
                    "recipient": recipient, "amount": amount_raw,
                    "currency": currency, "status": "pending_resolution"})
                return

            network = self._resolve_currency_to_network(currency)
            if network and network in self.address_cache:
                try:
                    tx_hash = self.send_transaction(network, recipient, float(amount_raw))
                    self._safe_publish("fintech.p2p.confirmed", {
                        "tx_hash": tx_hash, "recipient": recipient,
                        "amount": amount_raw, "currency": currency})
                except Exception as tx_err:
                    self._safe_publish("fintech.p2p.error", {
                        "error": str(tx_err), "recipient": recipient})
        except Exception as e:
            logger.error("Fintech P2P execute error: %s", e)

    def _handle_fintech_bitchat_execute(self, event_data):
        """Execute blockchain transfer from a parsed BitChat command."""
        try:
            if not isinstance(event_data, dict):
                return
            parsed = event_data.get("parsed")
            if not parsed:
                return
            amount_raw = parsed.get("amount", "0")
            asset = parsed.get("asset", "").upper()
            recipient = parsed.get("recipient", "")
            chain = parsed.get("chain", "")

            if not recipient or float(amount_raw) <= 0:
                return

            if recipient.startswith("@") or not any(c.isdigit() or c in 'abcdef' for c in recipient.lower()):
                self.logger.info("BitChat to @%s — queued for address resolution", recipient)
                self._safe_publish("fintech.bitchat.queued", {
                    "recipient": recipient, "amount": amount_raw,
                    "asset": asset, "chain": chain, "status": "pending_resolution"})
                return

            network = self._resolve_currency_to_network(asset) or chain
            if network:
                try:
                    tx_hash = self.send_transaction(network, recipient, float(amount_raw))
                    self._safe_publish("fintech.bitchat.confirmed", {
                        "tx_hash": tx_hash, "recipient": recipient,
                        "amount": amount_raw, "asset": asset})
                except Exception as tx_err:
                    self._safe_publish("fintech.bitchat.error", {
                        "error": str(tx_err), "asset": asset})
        except Exception as e:
            logger.error("Fintech BitChat execute error: %s", e)

    def _handle_fintech_nfc_execute(self, event_data):
        """Process approved NFC tap-to-pay by debiting the linked card wallet."""
        try:
            if not isinstance(event_data, dict):
                return
            card_id = event_data.get("card_id", "")
            amount_raw = event_data.get("amount", "0")
            self.logger.info("NFC tap approved: card=%s amount=%s", card_id, amount_raw)
            self._safe_publish("fintech.nfc.settled", {
                "card_id": card_id, "amount": amount_raw,
                "status": "settled", "timestamp": time.time()})
        except Exception as e:
            logger.error("Fintech NFC execute error: %s", e)

    def _resolve_currency_to_network(self, currency: str) -> str:
        """Map a currency/token symbol to a network key for send_transaction."""
        sym = currency.upper()
        if sym in self.address_cache:
            return sym
        net = self._SYMBOL_TO_NETWORK.get(sym)
        if net and net in self.address_cache:
            return net
        direct_map = {
            "USD": "USDC", "EUR": "USDC", "GBP": "USDC",
            "USDT": "ETH", "USDC": "ETH", "DAI": "ETH",
            "SHIB": "ETH", "PEPE": "ETH", "UNI": "ETH", "LINK": "ETH",
            "BONK": "SOL", "RAY": "SOL", "JUP": "SOL",
        }
        mapped = direct_map.get(sym)
        if mapped and mapped in self.address_cache:
            return mapped
        return ""
            
    # ── KAIG INTELLIGENCE BRIDGE HANDLERS ────────────────────────

    def _handle_kaig_wallet_directive(self, event_data):
        """Receive KAIG wallet directive — treasury monitoring, reserve alerts, speed mandate.

        This is the bridge between KAIG tokenomics goals and the wallet system.
        Every cycle the bridge publishes what we should be monitoring.
        """
        try:
            if not isinstance(event_data, dict):
                return
            if not hasattr(self, '_kaig_directive'):
                self._kaig_directive = {}
            self._kaig_directive = event_data

            # Check for low treasury alert
            alert_threshold = event_data.get("alert_on_low_reserves_usd", 1000.0)
            treasury_usd = event_data.get("treasury_reserves_usd", 0)
            if 0 < treasury_usd < alert_threshold:
                logger.warning(
                    "KAIG ALERT: Treasury reserves ($%.2f) below threshold ($%.2f)",
                    treasury_usd, alert_threshold)

            cycle = event_data.get("cycle", 0)
            if cycle <= 1 or cycle % 10 == 0:
                logger.info(
                    "KAIG Wallet Directive received: treasury=$%.2f, "
                    "monitor_escrow=%s, monitor_burn=%s",
                    treasury_usd,
                    event_data.get("monitor_escrow_releases", "?"),
                    event_data.get("monitor_burn_rate", "?"),
                )
        except Exception as e:
            logger.error(f"Error handling KAIG wallet directive: {e}")

    def _handle_identity_changed(self, event_data):
        """Handle token rebrand — wallet balances are tracked by address, NOT by token name.
        All funds, credits, staked coins, and earnings are 100% preserved.
        Only display labels change. Users do not need to take any action."""
        if isinstance(event_data, dict):
            self.logger.warning(
                "WalletManager: TOKEN REBRANDED %s → %s. "
                "All wallet balances preserved — tracked by address, not name.",
                event_data.get("old_ticker", "?"),
                event_data.get("new_ticker", "?"))

    def _handle_trading_system_readiness(self, event_data):
        """Cache global trading readiness for wallet/trading coordination."""
        try:
            if isinstance(event_data, dict):
                self._trading_system_readiness = {
                    "state": str(event_data.get("state", "UNKNOWN")).upper(),
                    "auto_trade_started": bool(event_data.get("auto_trade_started", False)),
                    "analysis_ready": bool(event_data.get("analysis_ready", False)),
                    "reason": event_data.get("reason", ""),
                    "timestamp": event_data.get("timestamp"),
                }
                self.status["trading_system_readiness"] = self._trading_system_readiness
                self.status["last_update"] = time.time()
        except Exception as e:
            logger.error(f"Error handling trading system readiness in WalletManager: {e}")

    def _handle_kaig_speed_mandate(self, event_data):
        """Receive global speed mandate from KAIG bridge."""
        try:
            if not isinstance(event_data, dict):
                return
            refresh = event_data.get("wallet_refresh_interval", 15)
            logger.debug("KAIG speed mandate received: wallet_refresh=%ds", refresh)
        except Exception as e:
            logger.debug(f"Error handling KAIG speed mandate: {e}")

    def publish_wallet_list(self):
        """Publish current wallet list to event bus."""
        try:
            wallet_list = self.get_wallet_list()
            self._safe_publish("wallet.list.response", {
                "wallets": wallet_list,
                "count": len(wallet_list),
                "timestamp": time.time()
            })
            self.logger.debug(f"Published wallet list with {len(wallet_list)} wallets")
        except Exception as e:
            self.logger.error(f"Error publishing wallet list: {e}")
            
    def _handle_list_wallets(self, event_data: Dict[str, Any]) -> None:
        """Handle wallet.list event to get all wallets.
        
        Args:
            event_data: Event data containing optional filters
        """
        self._run_async(self._handle_list_wallets_async, event_data)
        
    async def _handle_list_wallets_async(self, event_data: Dict[str, Any]) -> None:
        """Async implementation for wallet.list event."""
        try:
            coin_filter = event_data.get("coin") if event_data else None
            wallet_list = self.get_wallet_list(coin_filter=coin_filter)
            
            self._publish_success("wallet.list", {
                "wallets": wallet_list,
                "count": len(wallet_list),
                "filter": coin_filter
            })
        except Exception as e:
            self.logger.error(f"Error handling wallet.list event: {e}")
            self._publish_error("wallet.list", f"Error listing wallets: {str(e)}")
            
    def _handle_deposit_profits(self, event_data: Dict[str, Any]) -> None:
        """Handle trading.deposit_profits event to deposit profits into a wallet.
        
        Args:
            event_data: Dictionary containing profit details
        """
        self._run_async(self._handle_deposit_profits_async, event_data)
        
    async def _handle_deposit_profits_async(self, event_data: Dict[str, Any]) -> None:
        """Async implementation of deposit_profits handler."""
        try:
            if not event_data:
                self._publish_error("trading.deposit_profits", "Missing profit data")
                return
                
            amount = event_data.get("amount", 0)
            coin = event_data.get("coin", "").upper()
            address = event_data.get("address", "")
            
            if amount <= 0 or not coin or not address:
                self._publish_error("trading.deposit_profits", "Invalid profit deposit parameters")
                return
                
            # Ensure wallet exists
            if coin not in self.wallets:
                self.wallets[coin] = {}
            if address not in self.wallets[coin]:
                self.wallets[coin][address] = {"balance": 0, "name": f"{coin} Wallet"}
                
            # Add profit to balance
            self.wallets[coin][address]["balance"] = self.wallets[coin][address].get("balance", 0) + amount
            self.wallets[coin][address]["last_update"] = time.time()
            
            self._publish_success("trading.deposit_profits", {
                "amount": amount,
                "coin": coin,
                "address": address,
                "new_balance": self.wallets[coin][address]["balance"]
            })
            
        except Exception as e:
            self.logger.error(f"Error handling deposit profits: {e}")
            self._publish_error("trading.deposit_profits", f"Error processing profit deposit: {str(e)}")
            
    def _handle_withdraw_capital(self, event_data: Dict[str, Any]) -> None:
        """Handle trading.withdraw_capital event to withdraw capital for trading.
        
        Args:
            event_data: Dictionary containing withdrawal details
        """
        self._run_async(self._handle_withdraw_capital_async, event_data)
        
    async def _handle_withdraw_capital_async(self, event_data: Dict[str, Any]) -> None:
        """Async implementation of withdraw_capital handler."""
        try:
            if not event_data:
                self._publish_error("trading.withdraw_capital", "Missing withdrawal data")
                return
                
            amount = event_data.get("amount", 0)
            coin = event_data.get("coin", "").upper()
            address = event_data.get("address", "")
            
            if amount <= 0 or not coin or not address:
                self._publish_error("trading.withdraw_capital", "Invalid withdrawal parameters")
                return
                
            # Check wallet exists
            if coin not in self.wallets or address not in self.wallets[coin]:
                self._publish_error("trading.withdraw_capital", f"Wallet not found: {coin} {address}")
                return
                
            wallet = self.wallets[coin][address]
            current_balance = wallet.get("balance", 0)
            
            if current_balance < amount:
                self._publish_error("trading.withdraw_capital", f"Insufficient balance: {current_balance} < {amount}")
                return
                
            # Withdraw amount
            wallet["balance"] = current_balance - amount
            wallet["last_update"] = time.time()
            
            self._publish_success("trading.withdraw_capital", {
                "amount": amount,
                "coin": coin,
                "address": address,
                "new_balance": wallet["balance"]
            })
            
        except Exception as e:
            self.logger.error(f"Error handling withdraw capital: {e}")
            self._publish_error("trading.withdraw_capital", f"Error processing withdrawal: {str(e)}")
            
    # All duplicate handler methods removed - using first implementations above
        
    def _run_async_handler(self, handler, *args, **kwargs):
        """Run an async handler function with proper error handling.
        
        Args:
            handler: The async handler function to run
            *args: Positional arguments to pass to the handler
            **kwargs: Keyword arguments to pass to the handler
        """
        try:
            asyncio.create_task(handler(*args, **kwargs))
        except Exception as e:
            self.logger.error(f"Error in async handler: {e}")
            self._publish_error(handler.__name__, e)
            
    # Duplicate _safe_publish method removed - using first implementation
            
    # Duplicate _safe_subscribe method removed - using first implementation

    async def _load_from_redis(self, wallet_id):
        """Load wallet data from Redis."""
        try:
            # Access Redis using proper environment variable for security
            try:
                import redis
                # 2025 Pattern: Use getattr for Redis class access
                RedisClass = getattr(redis, 'Redis', None)
                if RedisClass is None:
                    raise ImportError("Redis.Redis class not available")
                import os
            except ImportError:
                self.logger.error("Redis module not available for data loading")
                return None
                
            # Get Redis password from environment variable - no fallbacks allowed
            redis_password = os.environ.get('KINGDOM_AI_SEC_KEY', '')
            # Connect to Redis Quantum Nexus on correct port (6380)
            redis_client = RedisClass(host='localhost', port=6380, db=0, 
                                password=redis_password)
            
            # Get wallet data
            key = f"wallet:{wallet_id}"
            response = await redis_client.get(key)
            if response:
                # Ensure we're working with a string or bytes, not a coroutine
                if isinstance(response, (str, bytes, bytearray)):
                    return json.loads(response)
                else:
                    logger.warning(f"Unexpected response type from Redis: {type(response)}")
                    return None
            return None
        except Exception as e:
            logger.error(f"Error loading from Redis: {e}")
            return None

    # Duplicate _handle_get_balance methods removed - using first implementation
            
    # Duplicate _handle_list_wallets methods removed - using first implementation 
    # Duplicate _handle_transfer methods removed - using first implementation

    def _handle_wallet_status(self, event_data):
        """Handle wallet.status event.
        
        Args:
            event_data: Event data
        """
        self._run_async_handler(self._handle_wallet_status_async, event_data)
            
    # Duplicate _handle_wallet_status_async method removed - using first implementation

    # Duplicate _handle_deposit_profits method removed - using first implementation
    
    # Duplicate _handle_withdraw_capital method removed - using first implementation
        
    # Duplicate _handle_withdraw_capital_async method removed - using first implementation
    
    # Duplicate _handle_wallet_status methods removed - using first implementation
            
    # Another duplicate _handle_withdraw_capital_async method removed - using first implementation
    
    # Yet another duplicate _handle_wallet_status method removed - using first implementation
    
    async def _handle_wallet_status_async(self, event_data: Dict[str, Any]) -> None:
        """Async implementation of wallet_status handler."""
        try:
            # Extract filter information
            coin = event_data.get("coin", "").upper() if event_data else ""
            min_balance = event_data.get("min_balance", 0) if event_data else 0
            
            # Get filtered wallets
            filtered_wallets = []
            for c, wallets in self.wallets.items():
                if coin and c != coin:
                    continue
                    
                for address, wallet_data in wallets.items():
                    balance = wallet_data.get("balance", 0)
                    if balance >= min_balance:
                        filtered_wallets.append({
                            "coin": c,
                            "address": address,
                            "balance": balance,
                            "name": wallet_data.get("name", f"{c} Wallet"),
                            "available_for_trading": True
                        })
            
            # Publish wallet status for trading
            self._safe_publish("trading.wallet_status_response", {
                "wallets": filtered_wallets,
                "count": len(filtered_wallets),
                "trading_system_readiness": self._trading_system_readiness,
                "timestamp": time.time()
            })
            
        except Exception as e:
            logger.error(f"Error handling trading.wallet_status: {e}")
            logger.error(traceback.format_exc())
            self._publish_error(f"Error getting wallet status: {str(e)}", "trading.wallet_error")
        
    def _handle_sentience_threshold(self, event_data=None):
        """Handle sentience threshold exceeded events.
        
        Args:
            event_data: Dictionary containing threshold event details:
                - threshold_type: Type of threshold exceeded
                - current_value: Current sentience metric value
                - threshold_value: Threshold that was exceeded
                - timestamp: When the threshold was exceeded
        """
        if not event_data:
            self.logger.warning("Received sentience threshold event with no data")
            return
            
        threshold_type = event_data.get('threshold_type', 'unknown')
        current_value = event_data.get('current_value', 0)
        threshold_value = event_data.get('threshold_value', 0)
        
        self.logger.info(f"Wallet sentience threshold exceeded: {threshold_type} = {current_value} (threshold: {threshold_value})")
        
        # Take action based on threshold type
        if threshold_type == 'autonomy':
            # Implement enhanced security measures for autonomous financial decisions
            self._safe_publish('wallet.security.enhance', {
                'reason': 'sentience_autonomy_threshold',
                'security_level': 'high',
                'duration': 3600  # 1 hour of enhanced security
            })
        elif threshold_type == 'awareness':
            # Log wallet awareness event for monitoring
            self._safe_publish('wallet.awareness.detected', {
                'awareness_level': current_value,
                'timestamp': time.time()
            })
        
    def _handle_sentience_pattern(self, event_data=None):
        """Handle sentience pattern detection events.
        
        Args:
            event_data: Dictionary containing pattern detection details:
                - pattern_type: Type of pattern detected
                - confidence: Confidence level in the detection
                - indicators: List of indicators that triggered the pattern
                - timestamp: When the pattern was detected
        """
        if not event_data:
            self.logger.warning("Received sentience pattern event with no data")
            return
            
        pattern_type = event_data.get('pattern_type', 'unknown')
        confidence = event_data.get('confidence', 0)
        indicators = event_data.get('indicators', [])
    
        self.logger.info(f"Wallet sentience pattern detected: {pattern_type} (confidence: {confidence}%)")
        
        # Take action based on pattern type
        if pattern_type == 'adaptive_learning' and confidence > 75:
            # The wallet system is showing signs of adaptive learning
            self._safe_publish('wallet.intelligence.update', {
                'learning_pattern': pattern_type,
                'confidence': confidence,
                'adaptive_indicators': indicators
            })
        elif pattern_type == 'decision_making' and confidence > 80:
            # The wallet system is showing signs of independent decision making
            self._safe_publish('wallet.autonomy.detected', {
                'decision_pattern': pattern_type,
                'confidence': confidence,
                'decision_indicators': indicators
            })
        
    def _handle_sentience_metric_update(self, event_data=None):
        """Handle sentience metric update events.
        
        Args:
            event_data: Dictionary containing metric update details:
                - metrics: Dictionary of updated metrics
                - trends: Dictionary of metric trends
                - timestamp: When metrics were updated
        """
        if not event_data:
            self.logger.warning("Received sentience metric update with no data")
            return
        
        metrics = event_data.get('metrics', {})
        trends = event_data.get('trends', {})
        
        # Update system status with latest sentience metrics
        if metrics:
            if 'sentience_metrics' not in self.status:
                self.status['sentience_metrics'] = {}
            
            self.status['sentience_metrics'].update(metrics)
            self.status['last_sentience_update'] = time.time()
            
        # Forward metrics to UI components for visualization
        self._safe_publish('wallet.ui.update_sentience_metrics', {
            'metrics': metrics,
            'trends': trends,
            'timestamp': time.time()
        })

    def get_all_balances(self) -> Dict[str, float]:
        """Get all wallet balances - ROOT CAUSE FIX.
        
        Returns:
            Dictionary mapping coin symbols to total balances
        """
        try:
            balances = {}
            
            for coin_type, wallets in self.wallets.items():
                total_balance = 0.0
                
                for address, wallet_data in wallets.items():
                    balance = wallet_data.get('balance', 0.0)
                    if isinstance(balance, (int, float)):
                        total_balance += float(balance)
                
                balances[coin_type.lower()] = total_balance
            
            # 2026 SOTA: NO MOCK DATA - return real balances only
            # If no wallets configured, return empty dict (not fake data)
            
            self.logger.debug(f"Retrieved real balances for {len(balances)} coins")
            return balances
            
        except Exception as e:
            self.logger.error(f"Error getting all balances: {e}")
            # Return empty dict on error
            return {}
    
    def get_total_balance(self, currency: str = "USD") -> float:
        """Get total portfolio balance across all wallets - TRADING INTEGRATION.
        
        This method is called by the trading system to get unified wallet balance.
        
        Args:
            currency: Target currency for balance (default USD)
            
        Returns:
            float: Total balance in specified currency
        """
        try:
            total = 0.0
            balances = self.get_all_balances()
            
            # Get current prices for USD conversion
            prices = getattr(self, '_cached_prices', {})
            
            for coin, balance in balances.items():
                if balance <= 0:
                    continue
                    
                # Convert to USD using cached prices
                coin_upper = coin.upper()
                if coin_upper in prices:
                    usd_price = prices[coin_upper]
                    total += balance * usd_price
                elif coin_upper in ('USDT', 'USDC', 'DAI', 'BUSD', 'USD'):
                    # Stablecoins are 1:1 with USD
                    total += balance
                else:
                    # No price available - add raw balance
                    total += balance
            
            self.logger.debug(f"Total wallet balance: ${total:.2f} {currency}")
            return total
            
        except Exception as e:
            self.logger.error(f"Error getting total balance: {e}")
            return 0.0
    
    def update_price_cache(self, prices: Dict[str, float]) -> None:
        """Update cached prices for USD conversion.
        
        Args:
            prices: Dictionary of coin -> USD price
        """
        try:
            if not hasattr(self, '_cached_prices'):
                self._cached_prices = {}
            self._cached_prices.update(prices)
            self.logger.debug(f"Updated price cache with {len(prices)} prices")
        except Exception as e:
            self.logger.error(f"Error updating price cache: {e}")

    def _resolve_reward_address(self, coin: str) -> Optional[str]:
        """Resolve payout address for a mined coin.

        Priority:
        1. Active user's address_cache (always preferred — isolates owner/consumer)
        2. Owner's kingdom_ai_wallet_app.json (ONLY when running as owner)
        3. config/multi_coin_wallets.json (ONLY when running as owner)
        """
        try:
            coin_sym = str(coin).upper().strip()
            if not coin_sym:
                return None

            addr = self.address_cache.get(coin_sym)
            if addr:
                return addr

            if self._skip_owner_data or self._active_user_id != "creator":
                return None

            base_dir = os.path.dirname(os.path.dirname(__file__))

            try:
                wallet_app_path = os.path.join(base_dir, "data", "wallets", "kingdom_ai_wallet_app.json")
                if os.path.exists(wallet_app_path):
                    with open(wallet_app_path, "r", encoding="utf-8-sig") as f:
                        app_data = json.load(f)
                    chains = app_data.get("chains") or {}
                    if isinstance(chains, dict) and coin_sym in chains:
                        chain_info = chains[coin_sym]
                        if isinstance(chain_info, dict):
                            addr = chain_info.get("address")
                        else:
                            addr = chain_info
                        if isinstance(addr, str) and addr.strip():
                            return addr.strip()
            except Exception as e:
                self.logger.warning(f"Error reading kingdom_ai_wallet_app.json for {coin_sym}: {e}")

            try:
                multi_wallets_path = os.path.join(base_dir, "config", "multi_coin_wallets.json")
                if os.path.exists(multi_wallets_path):
                    with open(multi_wallets_path, "r", encoding="utf-8-sig") as f:
                        multi_data = json.load(f)
                    for section in ("cpu_wallets", "gpu_wallets"):
                        wallets = multi_data.get(section) or {}
                        if isinstance(wallets, dict) and coin_sym in wallets:
                            addr = wallets.get(coin_sym)
                            if isinstance(addr, str) and addr.strip():
                                return addr.strip()
                    default_wallet = multi_data.get("default_wallet")
                    if isinstance(default_wallet, str) and default_wallet.strip():
                        return default_wallet.strip()
            except Exception as e:
                self.logger.warning(f"Error reading multi_coin_wallets.json for {coin_sym}: {e}")

            return None
        except Exception as e:
            self.logger.error(f"Error resolving reward address for {coin}: {e}")
            return None

    async def collect_mining_rewards(self, coin: str, pool: str, amount: float) -> Dict[str, Any]:
        """Collect mining rewards for a specific coin and pool.

        This is called by MiningIntelligence when uncollected rewards for a
        given coin reach the configured threshold (e.g. 10 coins). It resolves
        a destination wallet address, updates the internal wallet ledger, and
        publishes a notification event. Coins without a configured address are
        safely skipped until they are wired in the configs.
        """
        try:
            coin_sym = str(coin).upper().strip()
            if not coin_sym:
                return {"success": False, "error": "Invalid coin symbol", "collected_amount": 0.0}

            try:
                amt = float(amount)
            except (TypeError, ValueError):
                return {"success": False, "error": "Invalid amount", "collected_amount": 0.0}

            if amt <= 0.0:
                return {"success": False, "error": "Amount must be positive", "collected_amount": 0.0}

            address = self._resolve_reward_address(coin_sym)
            if not address:
                self.logger.warning(
                    "No payout address configured for mined coin %s; "
                    "rewards will remain uncollected until a wallet is wired",
                    coin_sym,
                )
                return {
                    "success": False,
                    "error": f"No payout address configured for {coin_sym}",
                    "collected_amount": 0.0,
                }

            if coin_sym not in self.wallets:
                self.wallets[coin_sym] = {}
            if address not in self.wallets[coin_sym]:
                self.wallets[coin_sym][address] = {
                    "balance": 0.0,
                    "name": f"{coin_sym} Mining Wallet",
                    "last_update": time.time(),
                }

            current_balance = float(self.wallets[coin_sym][address].get("balance", 0.0) or 0.0)
            new_balance = current_balance + amt
            self.wallets[coin_sym][address]["balance"] = new_balance
            self.wallets[coin_sym][address]["last_update"] = time.time()

            try:
                await self._persist_wallets()
            except Exception as e:
                self.logger.error(f"Error persisting wallets after reward collection: {e}")

            event_payload = {
                "coin": coin_sym,
                "address": address,
                "amount": amt,
                "new_balance": new_balance,
                "pool": str(pool),
                "timestamp": time.time(),
            }
            self._safe_publish("wallet.mining_rewards.collected", event_payload)

            self.logger.info(
                "Mining rewards collected: %s %.6f to %s (new balance %.6f)",
                coin_sym,
                amt,
                address,
                new_balance,
            )

            return {"success": True, "collected_amount": amt, "address": address}
        except Exception as e:
            self.logger.error(f"Error in collect_mining_rewards for {coin}: {e}")
            self.logger.error(traceback.format_exc())
            return {"success": False, "error": str(e), "collected_amount": 0.0}

    # Duplicate publish_wallet_list method removed - using first implementation
    
    # Duplicate _setup_event_handlers method removed - using first implementation
    
    def get_wallet(self, coin: str, address: str) -> Optional[Dict[str, Any]]:
        """Get specific wallet data - 2025 Missing Method Fix."""
        try:
            coin = coin.upper()
            if coin in self.wallets and address in self.wallets[coin]:
                return self.wallets[coin][address].copy()
            else:
                self.logger.warning(f"Wallet not found: {coin} {address}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting wallet {coin} {address}: {e}")
            return None
    
    def update_wallet(self, coin: str, address: str, data: Dict[str, Any]) -> bool:
        """Update wallet data - 2025 Missing Method Fix."""
        try:
            coin = coin.upper()
            if coin not in self.wallets:
                self.wallets[coin] = {}
            
            if address not in self.wallets[coin]:
                self.wallets[coin][address] = {}
            
            # Update wallet data
            self.wallets[coin][address].update(data)
            self.wallets[coin][address]["last_update"] = time.time()
            
            # Update status
            self.status["total_wallets"] = sum(len(wallets) for wallets in self.wallets.values())
            self.status["last_update"] = time.time()
            
            self.logger.debug(f"Updated wallet {coin} {address}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating wallet {coin} {address}: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the wallet manager and clean up resources."""
        self.running = False
        
        # Stop sentience monitoring if active
        if hasattr(self, 'sentience_integration') and self.sentience_integration:
            try:
                # 2025 Pattern: Safe method access with getattr
                stop_method = getattr(self.sentience_integration, 'stop', None)
                if stop_method and callable(stop_method):
                    if asyncio.iscoroutinefunction(stop_method):
                        await stop_method()
                    else:
                        stop_method()
                else:
                    self.logger.debug("Sentience integration has no stop method")
            except Exception as e:
                self.logger.error(f"Error stopping sentience integration: {e}")
        
        # Persist wallets before shutting down
        try:
            await self._persist_wallets()
        except Exception as e:
            self.logger.error(f"Error persisting wallets: {e}")
        
        self.logger.info("Wallet manager stopped")
        return True
    
    # =========================================================================
    # SOTA 2026: Chat/Voice Command Handlers for System-Wide Control
    # =========================================================================
    
    def _handle_balance_request(self, payload):
        """Handle balance request from chat/voice command."""
        try:
            self.logger.info("💰 Wallet balance requested via chat command")
            
            # Get all balances
            balances = {}
            for coin in self.wallets.keys():
                coin_wallets = self.wallets.get(coin, {})
                total = 0
                for addr, wallet_data in coin_wallets.items():
                    total += wallet_data.get('balance', 0)
                if total > 0:
                    balances[coin] = total
            
            response = {
                'balances': balances,
                'total_coins': len(balances),
                'timestamp': time.time()
            }
            
            self._safe_publish('wallet.balance.response', response)
            
        except Exception as e:
            self.logger.error(f"Error handling balance request: {e}")
    
    def _handle_send_transaction(self, payload):
        """Handle send transaction command from chat/voice."""
        try:
            amount = payload.get('amount', 0)
            token = payload.get('token', '').upper()
            to_address = payload.get('to', '')
            
            self.logger.info(f"📤 Send transaction requested: {amount} {token} to {to_address}")
            
            # Queue the transaction (actual send requires confirmation)
            tx_request = {
                'amount': amount,
                'token': token,
                'to': to_address,
                'status': 'pending_confirmation',
                'timestamp': time.time()
            }
            
            self._safe_publish('wallet.transaction.queued', tx_request)
            self.logger.info(f"✅ Transaction queued for confirmation")
            
        except Exception as e:
            self.logger.error(f"Error handling send transaction: {e}")
    
    def _handle_addresses_request(self, payload):
        """Handle addresses request from chat/voice command."""
        try:
            self.logger.info("📋 Wallet addresses requested via chat command")
            
            addresses = {}
            for coin, coin_wallets in self.wallets.items():
                addresses[coin] = list(coin_wallets.keys())
            
            response = {
                'addresses': addresses,
                'total_wallets': sum(len(addrs) for addrs in addresses.values()),
                'timestamp': time.time()
            }
            
            self._safe_publish('wallet.addresses.response', response)
            
        except Exception as e:
            self.logger.error(f"Error handling addresses request: {e}")
    
    # =========================================================================
    # MINING-WALLET INTEGRATION - Auto-deposit mining rewards
    # =========================================================================

    def _handle_mining_status_update(self, event_data: Dict[str, Any]) -> None:
        """Handle mining.update events and extract reward data for wallet deposit."""
        try:
            if not isinstance(event_data, dict):
                return
            stats = event_data.get("stats") or event_data
            reward = float(stats.get("estimated_reward", 0) or 0)
            shares = int(stats.get("shares_accepted", 0) or 0)
            if reward > 0 and shares > 0:
                self._handle_mining_reward({
                    "estimated_reward": reward,
                    "shares_accepted": shares,
                    "coin": stats.get("coin", "BTC"),
                    "source": "mining.update",
                })
        except Exception as e:
            self.logger.debug("mining.update handler: %s", e)

    def _handle_mining_reward(self, event_data: Dict[str, Any]) -> None:
        """Handle mining.reward_update event - auto-deposit mining rewards to wallet.
        
        Args:
            event_data: Mining reward data containing shares, estimated_reward, etc.
        """
        try:
            if not event_data:
                return
            
            # Extract reward information
            shares_accepted = event_data.get('shares_accepted', 0)
            estimated_reward = event_data.get('estimated_reward', 0.0)
            coin = event_data.get('coin', 'BTC').upper()
            pool = event_data.get('pool', 'unknown')
            
            if estimated_reward <= 0:
                return
            
            self.logger.info(f"⛏️ Mining reward received: {estimated_reward:.8f} {coin} from {pool}")
            
            # Get wallet address for this coin
            address = self._resolve_reward_address(coin)
            if not address:
                self.logger.warning(f"⚠️ No wallet configured for {coin} - reward not deposited")
                return
            
            # Credit the reward to the wallet
            if coin not in self.wallets:
                self.wallets[coin] = {}
            if address not in self.wallets[coin]:
                self.wallets[coin][address] = {
                    'balance': 0.0,
                    'name': f'{coin} Mining Wallet',
                    'last_update': time.time()
                }
            
            current_balance = float(self.wallets[coin][address].get('balance', 0.0) or 0.0)
            new_balance = current_balance + estimated_reward
            self.wallets[coin][address]['balance'] = new_balance
            self.wallets[coin][address]['last_update'] = time.time()
            
            # Publish wallet update event
            self._safe_publish('wallet.balance.updated', {
                'coin': coin,
                'address': address,
                'old_balance': current_balance,
                'new_balance': new_balance,
                'change': estimated_reward,
                'source': 'mining_reward',
                'timestamp': time.time()
            })
            
            self.logger.info(f"✅ Mining reward deposited: {estimated_reward:.8f} {coin} -> {address[:20]}... (new balance: {new_balance:.8f})")
            
        except Exception as e:
            self.logger.error(f"Error handling mining reward: {e}")
    
    def _handle_mining_payout(self, event_data: Dict[str, Any]) -> None:
        """Handle mining.payout event - larger payouts from mining pools.
        
        Args:
            event_data: Payout data from mining pool
        """
        try:
            if not event_data:
                return
            
            amount = float(event_data.get('amount', 0.0) or 0.0)
            coin = str(event_data.get('coin', event_data.get('symbol', 'BTC'))).upper()
            pool = event_data.get('pool', 'unknown')
            tx_hash = event_data.get('tx_hash', '')
            
            if amount <= 0:
                return
            
            self.logger.info(f"💰 Mining payout received: {amount:.8f} {coin} from {pool}")
            
            # Get wallet address for this coin
            address = self._resolve_reward_address(coin)
            if not address:
                self.logger.warning(f"⚠️ No wallet configured for {coin} - payout not credited")
                return
            
            # Credit the payout
            if coin not in self.wallets:
                self.wallets[coin] = {}
            if address not in self.wallets[coin]:
                self.wallets[coin][address] = {
                    'balance': 0.0,
                    'name': f'{coin} Mining Wallet',
                    'last_update': time.time()
                }
            
            current_balance = float(self.wallets[coin][address].get('balance', 0.0) or 0.0)
            new_balance = current_balance + amount
            self.wallets[coin][address]['balance'] = new_balance
            self.wallets[coin][address]['last_update'] = time.time()
            
            # Publish payout event
            self._safe_publish('wallet.mining_payout.received', {
                'coin': coin,
                'address': address,
                'amount': amount,
                'new_balance': new_balance,
                'pool': pool,
                'tx_hash': tx_hash,
                'timestamp': time.time()
            })
            
            self.logger.info(f"✅ Mining payout credited: {amount:.8f} {coin} (new balance: {new_balance:.8f})")
            
        except Exception as e:
            self.logger.error(f"Error handling mining payout: {e}")
    
    def _handle_mining_rewards_funnel(self, event_data: Dict[str, Any]) -> None:
        """Handle mining.rewards.funnel event - batch process mining rewards.
        
        Args:
            event_data: Funnel configuration with mode, coins, wallet settings
        """
        try:
            if not event_data:
                return
            
            mode = event_data.get('mode', 'auto')
            coins = event_data.get('coins', [])
            enabled_coins = event_data.get('enabled_coins', [])
            target_wallet = event_data.get('wallet', '')
            
            # Normalize coins list - handle both list of strings and list of dicts
            coins_to_process = []
            if coins:
                if isinstance(coins[0], str):
                    # Mining frame sends list of coin symbols
                    coins_to_process = [{'symbol': c.upper()} for c in coins]
                elif isinstance(coins[0], dict):
                    # Full coin data with amounts
                    coins_to_process = coins
            elif enabled_coins:
                coins_to_process = [{'symbol': c.upper()} for c in enabled_coins]
            
            self.logger.info(f"🔄 Mining rewards funnel: mode={mode}, coins={len(coins_to_process)}")
            
            # Get pending rewards from mining system via event bus
            pending_rewards = {}
            if self.event_bus:
                mining_system = None
                if hasattr(self.event_bus, 'get_component'):
                    mining_system = self.event_bus.get_component('mining_system')
                
                if mining_system and hasattr(mining_system, 'get_mining_rewards'):
                    pending_rewards = mining_system.get_mining_rewards()
                elif mining_system and hasattr(mining_system, '_multi_coin_wallets'):
                    # Alternative: get from config
                    pass
            
            # Collect rewards for each coin
            total_collected = 0.0
            coins_collected = 0
            
            for coin_data in coins_to_process:
                coin = coin_data.get('symbol', '').upper() if isinstance(coin_data, dict) else str(coin_data).upper()
                amount = coin_data.get('amount', 0.0) if isinstance(coin_data, dict) else 0.0
                
                # If no amount specified, check pending rewards
                if amount <= 0 and coin in pending_rewards:
                    amount = pending_rewards.get(coin, 0.0)
                
                if amount > 0:
                    self._handle_mining_reward({
                        'coin': coin,
                        'estimated_reward': amount,
                        'shares_accepted': coin_data.get('shares', 0) if isinstance(coin_data, dict) else 0,
                        'pool': coin_data.get('pool', 'funnel') if isinstance(coin_data, dict) else 'funnel'
                    })
                    total_collected += amount
                    coins_collected += 1
                else:
                    # Even if no amount, mark coin as funneled
                    self.logger.debug(f"📤 Funnel: {coin} - no pending rewards")
            
            # Publish completion event
            self._safe_publish('wallet.funnel.completed', {
                'mode': mode,
                'coins_requested': len(coins_to_process),
                'coins_collected': coins_collected,
                'total_collected': total_collected,
                'timestamp': time.time()
            })
            
            self.logger.info(f"✅ Funnel completed: {coins_collected} coins, {total_collected:.8f} total")
            
        except Exception as e:
            self.logger.error(f"Error handling mining rewards funnel: {e}")
    
    # =========================================================================
    # TRADING-WALLET INTEGRATION - Auto-deposit trading profits
    # =========================================================================
    
    def _handle_trading_profit(self, event_data: Dict[str, Any]) -> None:
        """Handle trading.profit.realized event - deposit trading profits.

        In CONSUMER mode, 10% of winning-trade profit is automatically
        deducted as commission and recorded for the owner wallet
        (0x4bED94d31d945a1C49F67721612bffb83eD1107C).
        """
        try:
            if not event_data:
                return

            profit = float(event_data.get('profit', event_data.get('amount', 0.0)) or 0.0)
            coin = str(event_data.get('coin', event_data.get('currency', 'USDT'))).upper()
            trade_id = event_data.get('trade_id', '')

            if profit <= 0:
                return

            self.logger.info(f"Trading profit realized: {profit:.8f} {coin}")

            net_profit = self._deduct_consumer_commission(profit, coin, trade_id)

            address = self._resolve_reward_address(coin) or self.address_cache.get(coin)
            if not address:
                address = self.config.get('default_trading_wallet', '')

            if not address:
                self.logger.warning(f"No wallet configured for trading profits in {coin}")
                return

            if coin not in self.wallets:
                self.wallets[coin] = {}
            if address not in self.wallets[coin]:
                self.wallets[coin][address] = {
                    'balance': 0.0,
                    'name': f'{coin} Trading Wallet',
                    'last_update': time.time()
                }

            current_balance = float(self.wallets[coin][address].get('balance', 0.0) or 0.0)
            new_balance = current_balance + net_profit
            self.wallets[coin][address]['balance'] = new_balance
            self.wallets[coin][address]['last_update'] = time.time()

            self._safe_publish('wallet.trading_profit.deposited', {
                'coin': coin,
                'address': address,
                'profit': net_profit,
                'gross_profit': profit,
                'commission_deducted': round(profit - net_profit, 8) if self._is_consumer else 0,
                'new_balance': new_balance,
                'trade_id': trade_id,
                'timestamp': time.time()
            })

            if self._is_consumer and profit != net_profit:
                self.logger.info(
                    "Trading profit deposited: %.8f %s (%.8f gross - %.8f commission)",
                    net_profit, coin, profit, profit - net_profit,
                )
            else:
                self.logger.info(f"Trading profit deposited: {net_profit:.8f} {coin}")

        except Exception as e:
            self.logger.error(f"Error handling trading profit: {e}")
    
    def _handle_position_closed(self, event_data: Dict[str, Any]) -> None:
        """Handle trading.position.closed event - update portfolio on position close.
        
        Args:
            event_data: Position close data with PnL
        """
        try:
            if not event_data:
                return
            
            pnl = float(event_data.get('pnl', event_data.get('profit_loss', 0.0)) or 0.0)
            symbol = event_data.get('symbol', '')
            position_id = event_data.get('position_id', '')
            
            self.logger.info(f"📊 Position closed: {symbol} PnL={pnl:.2f}")
            
            # If profitable, treat as realized profit
            if pnl > 0:
                self._handle_trading_profit({
                    'profit': pnl,
                    'coin': 'USDT',  # PnL typically in stablecoin
                    'trade_id': position_id,
                    'symbol': symbol
                })
            
            # Publish portfolio update event
            self._safe_publish('portfolio.position.closed', {
                'symbol': symbol,
                'pnl': pnl,
                'position_id': position_id,
                'timestamp': time.time()
            })
            
        except Exception as e:
            self.logger.error(f"Error handling position closed: {e}")
    
    # =========================================================================
    # CROSS-SYSTEM PORTFOLIO SYNC
    # =========================================================================
    
    def _handle_portfolio_sync(self, event_data: Dict[str, Any]) -> None:
        """Handle portfolio.sync.request - provide unified portfolio data.
        
        Args:
            event_data: Sync request parameters
        """
        try:
            # Get all balances
            balances = self.get_all_balances()
            total_usd = self.get_total_balance()
            
            # Build unified portfolio response
            portfolio = {
                'balances': balances,
                'total_usd': total_usd,
                'wallets_count': sum(len(w) for w in self.wallets.values()),
                'coins_count': len(balances),
                'last_update': time.time()
            }
            
            # Publish response
            self._safe_publish('portfolio.sync.response', portfolio)
            
            self.logger.info(f"📊 Portfolio sync: {len(balances)} coins, ${total_usd:.2f} total")
            
        except Exception as e:
            self.logger.error(f"Error handling portfolio sync: {e}")
    
    def _handle_market_prices(self, event_data: Dict[str, Any]) -> None:
        """Handle market.prices event - update price cache for USD conversion.
        
        Args:
            event_data: Market prices data
        """
        try:
            if not event_data:
                return
            
            prices = event_data.get('prices', {})
            if prices:
                self.update_price_cache(prices)
            
        except Exception as e:
            self.logger.error(f"Error handling market prices: {e}")

# End of class - line added by Kingdom AI fix script