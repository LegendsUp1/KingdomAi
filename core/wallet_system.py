#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI Wallet System Module

This module provides the core wallet system functionality for Kingdom AI.
Handles wallet creation, management, and blockchain interactions.
"""

import logging
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from core.wallet_creator import WalletCreator

logger = logging.getLogger(__name__)

@dataclass
class WalletInfo:
    """Wallet information structure"""
    address: str
    balance: float
    network: str
    wallet_type: str

class WalletSystem:
    """
    Core wallet system for Kingdom AI
    
    Provides wallet management, creation, and blockchain interaction
    capabilities for the Kingdom AI trading and mining system.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the wallet system"""
        self.event_bus = event_bus
        self.config = config or {}
        # In-memory registry: wallet_id -> metadata and chain addresses
        self.wallets: Dict[str, Dict[str, Any]] = {}
        self.active_wallet: Optional[str] = None
        self.logger = logger
        self.mining_stats: Dict[str, Any] = {}
        # WalletCreator / disk integration
        self._wallet_dir: Path = Path(self.config.get("wallet_dir", "data/wallets")).resolve()
        self._app_wallet_path: Path = self._wallet_dir / "kingdom_ai_wallet_app.json"
        self._wallet_creator: Optional[WalletCreator] = None
        
    async def initialize(self):
        """Initialize the wallet system"""
        try:
            self.logger.info("Initializing Kingdom AI Wallet System")
            # Load existing wallets
            await self._load_wallets()
            # Subscribe to mining statistics events for reward tracking
            if self.event_bus:
                try:
                    self.event_bus.subscribe("mining.stats.update", self.handle_mining_stats)
                    self.event_bus.subscribe("mining.rewards.funnel", self.handle_funnel_rewards)
                    self.logger.info("WalletSystem subscribed to mining.stats.update events")
                except Exception as e:
                    self.logger.error(f"Failed to subscribe to mining stats events: {e}")
            self.logger.info("✅ Wallet system initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize wallet system: {e}")
            return False
    
    async def _load_wallets(self):
        """Load existing wallets from WalletCreator and app-level descriptor.

        Builds a concrete multi-chain wallet registry from the
        kingdom_ai_wallet_app.json file and per-chain wallet JSONs
        managed by WalletCreator. No mock addresses are created here.
        """
        try:
            # Ensure wallet directory exists on disk
            self._wallet_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Unable to ensure wallet directory {self._wallet_dir}: {e}")
            self.wallets = {}
            return

        self.wallets = {}

        creator = self._get_wallet_creator()

        # Ensure the global Kingdom AI wallet exists and app descriptor is present
        try:
            await creator.create_kingdom_ai_wallet_if_missing(log_plaintext=False)
        except Exception as e:
            self.logger.error(f"Failed to create/load Kingdom AI wallet via WalletCreator: {e}")

        # Load the app-level descriptor (multi-chain view)
        try:
            if self._app_wallet_path.exists():
                with open(self._app_wallet_path, "r", encoding="utf-8-sig") as f:
                    app_data = json.load(f)

                wallet_id = app_data.get("id", "kingdom_ai_wallet")
                name = app_data.get("name", "Kingdom AI Wallet")
                created_at = app_data.get("created_at")

                addresses: Dict[str, str] = {}

                # Primary symbol codes like ETH, BTC, XMR, BONK, etc.
                chains = app_data.get("chains") or {}
                if isinstance(chains, dict):
                    for sym, info in chains.items():
                        addr = info.get("address") if isinstance(info, dict) else info
                        if isinstance(addr, str) and addr.strip():
                            addresses[str(sym).upper()] = addr.strip()

                # Legacy network keys (ethereum, bitcoin, etc.)
                base_addrs = app_data.get("addresses") or {}
                if isinstance(base_addrs, dict):
                    for net, addr in base_addrs.items():
                        if isinstance(addr, str) and addr.strip():
                            key = str(net).upper()
                            addresses.setdefault(key, addr.strip())

                self.wallets[wallet_id] = {
                    "id": wallet_id,
                    "name": name,
                    "created_at": created_at,
                    "addresses": addresses,
                    "balances": {},
                }
                self.active_wallet = wallet_id
        except Exception as e:
            self.logger.error(f"Error loading app-level wallet descriptor: {e}")

        # Merge any additional per-chain wallet JSONs discovered by WalletCreator
        raw_wallets: List[Dict[str, Any]] = []
        try:
            raw_wallets = await creator.list_wallets()
        except Exception as e:
            self.logger.error(f"Error listing wallets from WalletCreator: {e}")

        for entry in raw_wallets or []:
            try:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                blockchain = entry.get("blockchain")
                address = entry.get("address")
                if (
                    not name
                    or not blockchain
                    or not isinstance(address, str)
                    or not address.strip()
                ):
                    # Skip incomplete entries (e.g. descriptor-only JSONs)
                    continue

                wallet_id = str(name)
                chain_code = str(blockchain).upper()

                wallet = self.wallets.get(wallet_id) or {
                    "id": wallet_id,
                    "name": wallet_id,
                    "created_at": entry.get("created_at"),
                    "addresses": {},
                    "balances": {},
                }

                if chain_code not in wallet["addresses"]:
                    wallet["addresses"][chain_code] = address.strip()

                self.wallets[wallet_id] = wallet
            except Exception as e:
                self.logger.error(f"Error merging wallet entry from WalletCreator: {e}")

        self.logger.info(f"Loaded {len(self.wallets)} wallets from disk")

    def _get_wallet_creator(self) -> WalletCreator:
        """Lazily construct a WalletCreator bound to current config/event bus."""
        if self._wallet_creator is None:
            try:
                self._wallet_creator = WalletCreator(config=self.config, event_bus=self.event_bus)
            except Exception:
                self._wallet_creator = WalletCreator()
        return self._wallet_creator
    
    async def create_wallet(self, wallet_type="ethereum", name=None):
        """Create a new wallet using WalletCreator so a real address is generated.

        Returns the wallet_id string on success, or None on failure.
        """
        try:
            creator = self._get_wallet_creator()
            wallet_name = name or f"wallet_{int(time.time())}"

            # Map friendly names like "ethereum" -> "ETH" for WalletCreator
            wt = str(wallet_type or "ETH").strip().lower()
            if wt in ("eth", "ethereum"):
                chain_code = "ETH"
            elif wt in ("btc", "bitcoin"):
                chain_code = "BTC"
            elif wt in ("sol", "solana"):
                chain_code = "SOL"
            else:
                chain_code = wt.upper()

            result: Dict[str, Any] = await creator.create_wallet(wallet_name, blockchain=chain_code)
            if not isinstance(result, dict) or not result.get("success"):
                self.logger.error(f"WalletCreator failed to create wallet: {result}")
                return None

            address = result.get("address")
            if not isinstance(address, str) or not address.strip():
                self.logger.error("WalletCreator returned success but no address; refusing to register wallet")
                return None

            wallet_id = wallet_name
            wallet = self.wallets.get(wallet_id) or {
                "id": wallet_id,
                "name": wallet_id,
                "created_at": result.get("created_at"),
                "addresses": {},
                "balances": {},
            }
            wallet["addresses"][chain_code] = address.strip()
            self.wallets[wallet_id] = wallet

            if self.active_wallet is None:
                self.active_wallet = wallet_id

            self.logger.info(f"Created new wallet via WalletCreator: {wallet_id} ({chain_code})")
            return wallet_id
        except Exception as e:
            self.logger.error(f"Error creating wallet: {e}")
            return None
    
    def get_wallet_info(self, wallet_id):
        """Get wallet information"""
        return self.wallets.get(wallet_id)
    
    def get_address(self, wallet_id=None, network="ethereum"):
        """Get wallet address.
        
        Args:
            wallet_id: Wallet ID (uses active wallet if not provided)
            network: Network to get address for (default: ethereum)
            
        Returns:
            Wallet address string or None if not found
        """
        try:
            # Use active wallet if not specified
            if wallet_id is None:
                wallet_id = self.active_wallet
            
            if wallet_id is None:
                self.logger.warning("No wallet ID specified and no active wallet set")
                return None
            
            wallet = self.wallets.get(wallet_id)
            if not wallet:
                # Auto-create default wallet for common networks
                if wallet_id in ["ethereum", "bitcoin", "solana"]:
                    self.logger.info(f"Creating default {wallet_id} wallet...")
                    try:
                        # Load address from multi_coin_wallets.json
                        import json
                        from pathlib import Path
                        config_path = Path(__file__).parent.parent / 'config' / 'multi_coin_wallets.json'
                        if config_path.exists():
                            with open(config_path, 'r') as f:
                                wallet_config = json.load(f)
                                address = None
                                if wallet_id == "ethereum":
                                    address = wallet_config.get('gpu_wallets', {}).get('ETH')
                                elif wallet_id == "bitcoin":
                                    address = wallet_config.get('gpu_wallets', {}).get('BTC')
                                
                                if address:
                                    # Create wallet entry
                                    self.wallets[wallet_id] = {
                                        "id": wallet_id,
                                        "name": f"Kingdom AI {wallet_id.title()} Wallet",
                                        "address": address,
                                        "addresses": {wallet_id: address},
                                        "created_at": datetime.now().isoformat()
                                    }
                                    self.logger.info(f"✅ Created default {wallet_id} wallet: {address[:10]}...")
                                    return address
                    except Exception as create_err:
                        self.logger.debug(f"Could not auto-create wallet: {create_err}")
                
                self.logger.warning(f"Wallet not found: {wallet_id}")
                return None
            
            # Try to get address from wallet data
            address = wallet.get("address")
            if address:
                return address
            
            # Try network-specific address
            addresses = wallet.get("addresses", {})
            if isinstance(addresses, dict):
                network_lower = network.lower()
                if network_lower in addresses:
                    return addresses[network_lower]
            
            # Fallback to any available address
            if addresses and isinstance(addresses, dict):
                return next(iter(addresses.values()), None)
            
            self.logger.debug(f"No address found for wallet {wallet_id} on network {network}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting wallet address: {e}")
            return None
    
    def list_wallets(self):
        """List all wallets"""
        return list(self.wallets.keys())
    
    async def get_balance(self, wallet_id, network="ethereum"):
        """Get wallet balance.

        This method does not fabricate balances; it only returns values
        that have been populated into the wallet's "balances" mapping
        by upstream portfolio or blockchain components.
        """
        try:
            wallet = self.wallets.get(wallet_id)
            if not wallet:
                return 0.0

            balances = wallet.get("balances") or {}
            if not isinstance(balances, dict):
                return 0.0

            target = str(network or "").lower()
            for key, value in balances.items():
                try:
                    k = str(key)
                except Exception:
                    continue
                if k.lower() == target or k.upper() == target.upper():
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        return 0.0

            # No known balance for this network; return 0.0 without inventing data
            self.logger.debug(f"No recorded balance for wallet {wallet_id} on network {network}")
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return 0.0
    
    async def send_transaction(self, from_wallet, to_address, amount, network="ethereum"):
        """Send a transaction via WalletManager or event bus.

        Delegates to the WalletManager for real blockchain execution.
        Falls back to publishing a wallet.send event if no manager is available.
        """
        try:
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                wm = self.event_bus.get_component('wallet_manager')
                if wm and hasattr(wm, 'send_transaction'):
                    try:
                        tx_hash = wm.send_transaction(network, to_address, amount)
                        return {"status": "confirmed", "tx_hash": tx_hash,
                                "network": network, "amount": amount}
                    except Exception as tx_err:
                        return {"status": "error", "message": str(tx_err)}

            if self.event_bus:
                self.event_bus.publish("wallet.send", {
                    "to_address": to_address,
                    "amount": amount,
                    "network": network,
                    "source": "wallet_system",
                })
                return {"status": "submitted", "message": "Transaction submitted via event bus"}

            self.logger.error("No WalletManager or event bus available for send_transaction")
            return {"status": "error",
                    "message": "No blockchain provider available — configure WalletManager"}
        except Exception as e:
            self.logger.error(f"Error in send_transaction: {e}")
            return {"status": "error", "message": str(e)}
    
    def set_active_wallet(self, wallet_id):
        """Set the active wallet"""
        if wallet_id in self.wallets:
            self.active_wallet = wallet_id
            self.logger.info(f"Set active wallet to: {wallet_id}")
            return True
        return False
    
    def get_active_wallet(self):
        """Get the currently active wallet"""
        return self.active_wallet

    def get_tracked_wallets(self) -> List[Dict[str, Any]]:
        """Return a flat list of wallet addresses for integration layers.

        Each entry contains: wallet_id, name, address, network, and symbol.
        This is used by portfolio analytics and meme scanners to align
        on-chain holdings with market data.
        """
        tracked: List[Dict[str, Any]] = []
        try:
            for wallet_id, wallet in self.wallets.items():
                addresses = wallet.get("addresses") or {}
                if not isinstance(addresses, dict):
                    continue
                for chain_code, addr in addresses.items():
                    if not isinstance(addr, str) or not addr.strip():
                        continue
                    sym = str(chain_code).upper()
                    network = self._map_chain_to_network(sym)
                    tracked.append(
                        {
                            "wallet_id": wallet_id,
                            "name": wallet.get("name", wallet_id),
                            "address": addr.strip(),
                            "network": network,
                            "symbol": sym,
                        }
                    )
        except Exception as e:
            self.logger.error(f"Error building tracked wallet list: {e}")
        return tracked

    @staticmethod
    def _map_chain_to_network(symbol: str) -> str:
        """Best-effort mapping from chain symbol (ETH, BTC, SOL, XRP, BONK) to network key."""
        sym = (symbol or "").upper()
        mapping = {
            "ETH": "ethereum",
            "WETH": "ethereum",
            "BTC": "bitcoin",
            "WBTC": "bitcoin",
            "SOL": "solana",
            "BONK": "solana",
            "MATIC": "polygon",
            "POL": "polygon",
            "BNB": "bsc",
            "AVAX": "avalanche",
            "ARB": "arbitrum",
            "OP": "optimism",
            "BASE": "base",
            "XRP": "xrp",
            "XMR": "monero",
        }
        if sym in mapping:
            return mapping[sym]
        return sym.lower() or "unknown"
    
    async def shutdown(self):
        """Shutdown the wallet system"""
        try:
            self.logger.info("Shutting down wallet system")
            # Save wallet state
            await self._save_wallets()
        except Exception as e:
            self.logger.error(f"Error during wallet system shutdown: {e}")
    
    async def _save_wallets(self):
        """Save wallets to storage.

        This persists a non-sensitive runtime snapshot (addresses,
        balances, metadata) alongside WalletCreator-managed files. No
        seed phrases or private keys are written here.
        """
        try:
            state_path = self._wallet_dir / "wallet_runtime_state.json"
            serializable: Dict[str, Any] = {}
            for wid, w in self.wallets.items():
                try:
                    serializable[wid] = {
                        "id": w.get("id", wid),
                        "name": w.get("name", wid),
                        "created_at": w.get("created_at"),
                        "addresses": w.get("addresses", {}),
                        "balances": w.get("balances", {}),
                    }
                except Exception:
                    continue

            try:
                self._wallet_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving wallets: {e}")

    async def handle_mining_stats(self, data: Dict[str, Any]):
        """Handle mining reward statistics events from the MiningSystem.

        Stores the latest stats snapshot and forwards a wallet-specific
        event that the GUI can subscribe to for richer per-coin tracking.
        """
        try:
            stats = data.get("stats") if isinstance(data, dict) else None
            if stats is None:
                stats = {}
            self.mining_stats = stats

            if self.event_bus:
                try:
                    self.event_bus.publish("wallet.mining_stats.updated", {
                        "wallet_id": self.active_wallet or "kingdom_ai_wallet",
                        "stats": stats,
                        "timestamp": time.time()
                    })
                except Exception as e:
                    self.logger.error(f"Failed to publish wallet.mining_stats.updated: {e}")
        except Exception as e:
            self.logger.error(f"Error handling mining stats event: {e}")

    async def handle_funnel_rewards(self, data: Dict[str, Any]):
        try:
            if not isinstance(data, dict):
                data = {}
            mode_raw = data.get("mode")
            mode = str(mode_raw).lower() if mode_raw is not None else "all"
            coins_raw = data.get("coins") or data.get("enabled_coins") or []
            if isinstance(coins_raw, dict):
                symbols_iter = coins_raw.keys()
            else:
                symbols_iter = coins_raw
            enabled_coins: List[str] = []
            for symbol in symbols_iter:
                if not symbol:
                    continue
                sym = str(symbol).strip()
                if not sym:
                    continue
                enabled_coins.append(sym.upper())
            stats_snapshot = self.mining_stats if isinstance(self.mining_stats, dict) else {}
            wallet_id = self.active_wallet or "kingdom_ai_wallet"
            self.logger.info(
                "Received mining.rewards.funnel request: mode=%s coins=%s wallet=%s",
                mode,
                enabled_coins,
                wallet_id,
            )
            if self.event_bus:
                try:
                    self.event_bus.publish(
                        "wallet.rewards.funnel.requested",
                        {
                            "wallet_id": wallet_id,
                            "mode": mode,
                            "coins": enabled_coins,
                            "stats": stats_snapshot,
                            "timestamp": time.time(),
                        },
                    )
                except Exception as e:
                    self.logger.error(f"Failed to publish wallet.rewards.funnel.requested: {e}")
        except Exception as e:
            self.logger.error(f"Error handling mining.rewards.funnel event: {e}")

    def get_transactions(self, network: str = "ethereum", limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get transaction history for a specific network.
        
        Args:
            network: Blockchain network name (default: ethereum)
            limit: Maximum number of transactions to return
            
        Returns:
            List of transaction dictionaries
        """
        try:
            # Get wallet address for the network
            wallet_id = self.active_wallet
            if not wallet_id:
                self.logger.warning("No active wallet set")
                return []
            
            address = self.get_address(wallet_id, network)
            if not address:
                self.logger.warning(f"No address found for {network}")
                return []
            
            # Try to get transactions via WalletManager if available
            if self.event_bus and hasattr(self.event_bus, 'get_component'):
                wm = self.event_bus.get_component('wallet_manager')
                if wm and hasattr(wm, 'get_transaction_history'):
                    try:
                        transactions = wm.get_transaction_history(network, address, limit)
                        return transactions if transactions else []
                    except Exception as tx_err:
                        self.logger.debug(f"WalletManager transaction history failed: {tx_err}")
            
            # Fallback: Query blockchain explorer API
            import urllib.request
            import json
            
            network_lower = network.lower()
            if network_lower in ["ethereum", "eth"]:
                # Use Etherscan API
                api_url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset={limit}&sort=desc"
            elif network_lower in ["bitcoin", "btc"]:
                # Use Blockstream API
                api_url = f"https://blockstream.info/api/address/{address}/txs"
            elif network_lower in ["solana", "sol"]:
                # Use Solscan API (public, no key needed for basic queries)
                api_url = f"https://public-api.solscan.io/account/transactions?account={address}&limit={limit}"
            else:
                self.logger.warning(f"Transaction history not supported for {network}")
                return []
            
            try:
                request = urllib.request.Request(api_url)
                with urllib.request.urlopen(request, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    
                    if network_lower in ["ethereum", "eth"]:
                        if data.get("status") == "1" and data.get("result"):
                            return data["result"][:limit]
                    elif network_lower in ["bitcoin", "btc"]:
                        if isinstance(data, list):
                            return data[:limit]
                    elif network_lower in ["solana", "sol"]:
                        if isinstance(data, list):
                            return data[:limit]
                    
                    return []
            except Exception as api_error:
                self.logger.error(f"Failed to fetch transactions from explorer: {api_error}")
                return []
        except Exception as e:
            self.logger.error(f"Error getting transactions for {network}: {e}")
            return []


if __name__ == "__main__":
    async def _run_kingdom_ai_wallet_creation() -> None:
        """CLI entrypoint: create or refresh the Kingdom AI wallet.

        This will ensure that kingdom_ai_wallet_app.json is regenerated using
        the current BIP39 seed, HD engine, EVM reuse, Monero adapter, and any
        external CLI wallet commands defined in config/wallet_external.json.
        """

        creator = WalletCreator()
        result: Dict[str, Any] = await creator.create_kingdom_ai_wallet_if_missing()
        # Print a compact JSON summary so the caller can inspect success
        try:
            print(json.dumps(result, indent=2))
        except Exception:
            print(result)

    asyncio.run(_run_kingdom_ai_wallet_creation())
