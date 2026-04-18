#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Multi-chain trading executor skeleton built on top of kingdomweb3_v2.

This module provides a read-only, network-aware interface for all blockchains
listed in kingdomweb3_v2.COMPLETE_BLOCKCHAIN_NETWORKS, plus minimal balance
queries for EVM-compatible chains. Swap/DEX execution is intentionally left as
clearly-marked stubs so that per-chain DEX logic can be added safely later.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from decimal import Decimal

import aiohttp
from cryptography.fernet import Fernet
from eth_account import Account

from kingdomweb3_v2 import (
    COMPLETE_BLOCKCHAIN_NETWORKS,
    create_web3_instance,
    create_async_web3_instance,
    Web3,
    AsyncWeb3,
)

try:
    from core.event_bus import EventBus
except Exception:  # pragma: no cover - optional dependency
    EventBus = None  # type: ignore


@dataclass
class ChainStatus:
    name: str
    rpc_url: str
    is_evm: bool
    reachable: bool
    latest_block: Optional[int] = None
    error: Optional[str] = None


def load_rpc_overrides_from_comprehensive_config(
    config_path: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, str]:
    """Build a mapping of chain_id -> preferred RPC URL from the comprehensive config.

    This helper reads config/comprehensive_blockchain_config.json and constructs
    a dict suitable for the ``rpc_overrides`` argument of MultiChainTradeExecutor.

    It prefers endpoints that are explicitly listed under "rpc_endpoints" for
    each network and will map them onto the identifiers used in
    COMPLETE_BLOCKCHAIN_NETWORKS by matching either the chain_id or, when
    available, the network key name.
    """

    log = logger or logging.getLogger(__name__)

    if config_path is None:
        # Resolve the default config path relative to this module:
        #   core/multichain_trade_executor.py -> project root -> config/...
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config", "comprehensive_blockchain_config.json")

    overrides: Dict[str, str] = {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    except Exception as exc:  # pragma: no cover - file/IO dependent
        log.warning("Could not load comprehensive blockchain config from %s: %s", config_path, exc)
        return overrides

    by_chain_id: Dict[int, List[str]] = {}
    by_name: Dict[str, List[str]] = {}

    def _collect_endpoints(section_name: str) -> None:
        section = config_data.get(section_name)
        if not isinstance(section, dict):
            return
        for key, cfg in section.items():
            if not isinstance(cfg, dict):
                continue
            endpoints = cfg.get("rpc_endpoints")
            if not isinstance(endpoints, list):
                continue
            urls: List[str] = [
                url
                for url in endpoints
                if isinstance(url, str) and url.startswith(("http://", "https://"))
            ]
            if not urls:
                continue

            chain_id = cfg.get("chain_id")
            if isinstance(chain_id, int):
                by_chain_id.setdefault(chain_id, urls)

            by_name.setdefault(key, urls)

    for section_name in ("primary_networks", "layer2_networks", "bitcoin_networks"):
        _collect_endpoints(section_name)

    from kingdomweb3_v2 import COMPLETE_BLOCKCHAIN_NETWORKS  # local import to avoid cycles

    for chain_key, base_cfg in COMPLETE_BLOCKCHAIN_NETWORKS.items():
        if not isinstance(base_cfg, dict):
            continue

        candidates: List[str] = []
        chain_id = base_cfg.get("chain_id")
        if isinstance(chain_id, int) and chain_id in by_chain_id:
            candidates = by_chain_id[chain_id]
        elif chain_key in by_name:
            candidates = by_name[chain_key]

        if not candidates:
            continue

        existing_url = base_cfg.get("rpc_url")
        chosen: Optional[str] = None
        for url in candidates:
            if not url:
                continue
            if url != existing_url:
                chosen = url
                break
        if chosen is None:
            chosen = candidates[0]

        overrides[chain_key] = chosen
        log.debug("RPC override for %s: %s -> %s", chain_key, existing_url, chosen)

    log.info("Loaded %d RPC overrides from comprehensive_blockchain_config.json", len(overrides))
    return overrides


class MultiChainTradeExecutor:
    """Skeleton multi-chain executor using kingdomweb3_v2 networks.

    This class is intentionally conservative: it focuses on network discovery
    and basic balance queries for EVM chains. Methods for quoting and executing
    swaps are present but raise NotImplementedError so that concrete DEX
    integrations can be added per-chain without ambiguity.
    """

    def __init__(
        self,
        rpc_overrides: Optional[Dict[str, str]] = None,
        event_bus: Optional[EventBus] = None,  # type: ignore[valid-type]
        logger: Optional[logging.Logger] = None,
        default_from_address: Optional[str] = None,
        default_private_key: Optional[str] = None,
        dex_router_overrides: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> None:
        self.rpc_overrides: Dict[str, str] = rpc_overrides or {}
        self.event_bus = event_bus
        self.logger = logger or logging.getLogger(__name__)

        # Cached EVM signing wallet and Web3 instances for on-chain swaps.
        self._evm_address: Optional[str] = None
        self._evm_private_key: Optional[str] = None
        self._web3_cache: Dict[str, Web3] = {}

        # Per-chain DEX router configuration (Uniswap‑V2‑compatible by default).
        self.dex_routers: Dict[str, Dict[str, str]] = self._build_default_dex_router_config()
        if dex_router_overrides:
            self.dex_routers.update(dex_router_overrides)

        if default_from_address:
            self._evm_address = default_from_address
        if default_private_key:
            # Allow callers to pass either with or without 0x prefix.
            self._evm_private_key = (
                default_private_key[2:] if default_private_key.startswith("0x") else default_private_key
            )

        # If no explicit wallet was provided, try to load the Kingdom AI ETH wallet.
        if not self._evm_address or not self._evm_private_key:
            self._load_default_evm_wallet()

    # ------------------------------------------------------------------
    # Network discovery
    # ------------------------------------------------------------------
    def get_supported_networks(self) -> List[str]:
        """Return all blockchain identifiers known to kingdomweb3_v2."""

        return list(COMPLETE_BLOCKCHAIN_NETWORKS.keys())

    def get_chain_config(self, chain: str) -> Optional[Dict[str, Any]]:
        """Get raw network configuration for a chain identifier."""

        cfg = COMPLETE_BLOCKCHAIN_NETWORKS.get(chain)
        if not cfg:
            return None
        cfg = dict(cfg)
        if chain in self.rpc_overrides:
            cfg["rpc_url"] = self.rpc_overrides[chain]
        return cfg

    async def get_chain_status(self, chain: str) -> ChainStatus:
        """Check basic reachability and latest block for a chain.

        For EVM-compatible networks, this attempts an ``eth_blockNumber`` call.
        For non-EVM chains, it performs a lightweight HTTP probe to the RPC URL.
        """

        cfg = self.get_chain_config(chain)
        if not cfg:
            return ChainStatus(
                name=chain,
                rpc_url="",
                is_evm=False,
                reachable=False,
                error="unknown chain",
            )

        rpc_url = cfg.get("rpc_url", "")
        is_evm = bool(cfg.get("is_evm", True))

        if not rpc_url:
            return ChainStatus(
                name=chain,
                rpc_url="",
                is_evm=is_evm,
                reachable=False,
                error="missing rpc_url",
            )

        if not is_evm:
            # Non-EVM chains: perform a lightweight HTTP reachability probe.
            reachable_non_evm = False
            error_non_evm: Optional[str] = None
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    try:
                        async with session.get(rpc_url) as resp:
                            # Any HTTP response indicates basic reachability, even
                            # if the status is not 200 (some RPCs require POST).
                            reachable_non_evm = True
                    except Exception as exc:
                        error_non_evm = f"http probe failed: {exc}"
            except Exception as exc:
                error_non_evm = f"session init failed: {exc}"

            return ChainStatus(
                name=chain,
                rpc_url=rpc_url,
                is_evm=False,
                reachable=reachable_non_evm,
                error=error_non_evm,
            )

        # EVM-compatible network: attempt eth_blockNumber via synchronous
        # Web3 in a background thread. This avoids leaking aiohttp client
        # sessions from AsyncWeb3 providers while still exercising the
        # underlying RPC connectivity.
        latest_block: Optional[int] = None
        error: Optional[str] = None
        reachable = False

        try:
            w3: Optional[Web3] = create_web3_instance(rpc_url)
        except Exception as exc:  # pragma: no cover - network dependent
            w3 = None
            error = f"create_web3_instance failed: {exc}"

        if w3 is not None:
            try:
                def _get_block() -> Optional[int]:
                    try:
                        # Newer Web3 versions expose ``block_number`` as an int
                        return int(w3.eth.block_number)  # type: ignore[attr-defined]
                    except Exception:
                        # Fallback for any older attribute naming
                        try:
                            return int(getattr(w3.eth, "blockNumber"))  # type: ignore[arg-type]
                        except Exception:
                            return None

                latest_candidate = await asyncio.to_thread(_get_block)
                if isinstance(latest_candidate, int):
                    latest_block = latest_candidate
                    reachable = True
            except Exception as exc:  # pragma: no cover - network dependent
                error = f"eth.block_number failed: {exc}"

        return ChainStatus(
            name=chain,
            rpc_url=rpc_url,
            is_evm=is_evm,
            reachable=reachable,
            latest_block=latest_block,
            error=error,
        )

    # ------------------------------------------------------------------
    # Balances (EVM only for now)
    # ------------------------------------------------------------------
    async def get_native_balance(self, chain: str, address: str) -> float:
        """Get native currency balance on an EVM-compatible chain.

        Returns the balance in whole units (e.g. ETH, BNB) or ``0.0`` on
        error or for non-EVM chains.
        """

        cfg = self.get_chain_config(chain)
        if not cfg or not cfg.get("rpc_url"):
            return 0.0
        if not cfg.get("is_evm", True):
            return 0.0

        rpc_url = cfg["rpc_url"]
        try:
            async_w3: Optional[AsyncWeb3] = create_async_web3_instance(rpc_url)
        except Exception:  # pragma: no cover - network dependent
            async_w3 = None

        if async_w3 is None:
            return 0.0

        try:
            balance_wei = await async_w3.eth.get_balance(address)  # type: ignore[attr-defined]
            if isinstance(balance_wei, int):
                return balance_wei / 10**18
        except Exception:  # pragma: no cover - network dependent
            return 0.0
        return 0.0

    async def get_erc20_balance(self, chain: str, token_address: str, holder: str) -> float:
        """Get ERC-20 token balance on an EVM-compatible chain.

        This uses a minimal ABI for ``balanceOf`` and ``decimals``. On any
        error or for non-EVM chains, ``0.0`` is returned.
        """

        cfg = self.get_chain_config(chain)
        if not cfg or not cfg.get("rpc_url"):
            return 0.0
        if not cfg.get("is_evm", True):
            return 0.0

        rpc_url = cfg["rpc_url"]
        try:
            w3: Optional[Web3] = create_web3_instance(rpc_url)
        except Exception:  # pragma: no cover - network dependent
            w3 = None

        if w3 is None:
            return 0.0

        erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            },
        ]

        try:
            contract = w3.eth.contract(address=token_address, abi=erc20_abi)  # type: ignore[union-attr]
            raw_balance = contract.functions.balanceOf(holder).call()
            decimals = contract.functions.decimals().call()
            if isinstance(raw_balance, int) and isinstance(decimals, int) and decimals >= 0:
                return raw_balance / (10**decimals)
        except Exception:  # pragma: no cover - network dependent
            return 0.0
        return 0.0

    # ------------------------------------------------------------------
    # Internal helpers for on-chain DEX execution (EVM only)
    # ------------------------------------------------------------------
    def _build_default_dex_router_config(self) -> Dict[str, Dict[str, str]]:
        """Return default DEX router config mapping chain -> {type, address}.

        The defaults target Uniswap‑V2‑compatible routers on major EVM chains.
        Callers can override or extend this via ``dex_router_overrides``.
        """

        return {
            # Ethereum mainnet - Uniswap V2 router
            "ethereum": {
                "type": "uniswap_v2",
                "address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            },
            # BNB Smart Chain - PancakeSwap V2 router
            "bsc": {
                "type": "uniswap_v2",
                "address": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
            },
            # Polygon PoS - QuickSwap router
            "polygon": {
                "type": "uniswap_v2",
                "address": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
            },
            # Arbitrum One - SushiSwap router
            "arbitrum": {
                "type": "uniswap_v2",
                "address": "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506",
            },
            # Optimism - Uniswap universal router (V2/V3‑compatible interface)
            "optimism": {
                "type": "uniswap_v2",
                "address": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
            },
        }

    def _get_web3_for_chain(self, chain: str) -> Optional[Web3]:
        """Return or create a cached Web3 instance for an EVM chain."""

        cfg = self.get_chain_config(chain)
        if not cfg or not cfg.get("is_evm", True):
            return None
        rpc_url = cfg.get("rpc_url")
        if not rpc_url:
            return None

        w3 = self._web3_cache.get(chain)
        if w3 is None:
            w3 = create_web3_instance(rpc_url, network_name=chain)
            if w3 is None:
                return None
            self._web3_cache[chain] = w3
        return w3

    def _load_default_evm_wallet(self) -> None:
        """Load the Kingdom AI ETH wallet for signing on-chain swaps, if present.

        This reads data/wallets/kingdom_ai_wallet_ETH.json and decrypts the
        private key using the symmetric key stored in data/.encryption_key.
        """

        if self._evm_address and self._evm_private_key:
            return

        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            wallet_path = os.path.join(base_dir, "data", "wallets", "kingdom_ai_wallet_ETH.json")
            key_path = os.path.join(base_dir, "data", ".encryption_key")

            if not os.path.exists(wallet_path) or not os.path.exists(key_path):
                self.logger.warning(
                    "Kingdom AI ETH wallet files not found; provide default_from_address and "
                    "default_private_key to enable on-chain swaps."
                )
                return

            with open(wallet_path, "r", encoding="utf-8-sig") as f:
                wdata = json.load(f)
            address = wdata.get("address")
            enc_priv = wdata.get("encrypted_private_key")
            if not isinstance(address, str) or not isinstance(enc_priv, str):
                self.logger.warning(
                    "kingdom_ai_wallet_ETH.json is missing address or encrypted_private_key; on-chain swaps disabled"
                )
                return

            with open(key_path, "rb") as f:
                key_bytes = f.read()

            fernet = Fernet(key_bytes)
            priv_hex = fernet.decrypt(enc_priv.encode("utf-8")).decode("utf-8")
            if priv_hex.startswith("0x"):
                priv_hex = priv_hex[2:]

            if Web3 is not None:
                try:
                    address = Web3.to_checksum_address(address)
                except Exception:
                    pass

            self._evm_address = address
            self._evm_private_key = priv_hex
            self.logger.info("Loaded default EVM signing wallet for multichain swaps: %s", address)
        except Exception as exc:
            self.logger.error("Failed to load default EVM wallet for multichain swaps: %s", exc)

    def _ensure_evm_wallet(self) -> None:
        """Ensure an EVM signing wallet is available, or raise a clear error."""

        if not self._evm_address or not self._evm_private_key:
            self._load_default_evm_wallet()
        if not self._evm_address or not self._evm_private_key:
            raise RuntimeError(
                "No EVM signing wallet is configured for MultiChainTradeExecutor. "
                "Provide default_from_address/private_key at construction time or "
                "create the Kingdom AI wallet via wallet_creator."
            )

    def _get_erc20_contract(self, w3: Web3, token_address: str):
        """Return a minimal ERC‑20 contract wrapper for balance/decimals/allowance/approve."""

        erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"},
                ],
                "name": "allowance",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"},
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function",
            },
        ]
        return w3.eth.contract(address=token_address, abi=erc20_abi)

    # ------------------------------------------------------------------
    # Swap/DEX execution
    # ------------------------------------------------------------------
    async def quote_swap(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: float,
    ) -> Dict[str, Any]:
        """Return a swap quote on the given chain using a configured DEX router.

        Currently implemented for EVM chains only via Uniswap‑V2‑style routers.
        """

        cfg = self.get_chain_config(chain)
        if not cfg:
            raise ValueError(f"Unknown chain: {chain}")
        if not cfg.get("is_evm", True):
            if chain.lower() == "solana":
                return await self._quote_swap_solana(token_in, token_out, amount_in, cfg)
            raise ValueError(
                f"DEX swaps on {chain} are not available. "
                f"Supported: EVM chains (Ethereum, BSC, Polygon, Arbitrum, Optimism) and Solana."
            )

        router_info = self.dex_routers.get(chain)
        if not router_info:
            raise ValueError(f"No DEX router configured for chain {chain}. Add one via set_dex_router().")

        w3 = self._get_web3_for_chain(chain)
        if w3 is None:
            raise RuntimeError(f"Failed to create Web3 instance for chain {chain}")

        router_address = router_info["address"]
        if Web3 is not None:
            try:
                router_address = Web3.to_checksum_address(router_address)
            except Exception:
                pass

        # Minimal Uniswap V2 router ABI: getAmountsOut(amountIn, path)
        router_abi = [
            {
                "name": "getAmountsOut",
                "outputs": [{"name": "", "type": "uint256[]"}],
                "inputs": [
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "path", "type": "address[]"},
                ],
                "stateMutability": "view",
                "type": "function",
            },
        ]
        router = w3.eth.contract(address=router_address, abi=router_abi)

        # Normalise token addresses and fetch decimals.
        if Web3 is not None:
            try:
                token_in = Web3.to_checksum_address(token_in)
                token_out = Web3.to_checksum_address(token_out)
            except Exception:
                pass

        in_contract = self._get_erc20_contract(w3, token_in)
        out_contract = self._get_erc20_contract(w3, token_out)

        decimals_in = int(in_contract.functions.decimals().call())
        decimals_out = int(out_contract.functions.decimals().call())

        amount_in_wei = int(Decimal(str(amount_in)) * (Decimal(10) ** decimals_in))
        path = [token_in, token_out]

        try:
            amounts = router.functions.getAmountsOut(amount_in_wei, path).call()
        except Exception as exc:
            raise RuntimeError(f"Router getAmountsOut failed on {chain}: {exc}") from exc

        if not isinstance(amounts, (list, tuple)) or len(amounts) < 2:
            raise RuntimeError("Unexpected router.getAmountsOut response")

        amount_out_wei = int(amounts[-1])
        amount_out = float(Decimal(amount_out_wei) / (Decimal(10) ** decimals_out))

        return {
            "status": "ok",
            "chain": chain,
            "router": router_address,
            "token_in": token_in,
            "token_out": token_out,
            "amount_in": float(amount_in),
            "amount_in_wei": str(amount_in_wei),
            "amount_out": amount_out,
            "amount_out_wei": str(amount_out_wei),
            "path": path,
        }

    async def execute_swap(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: float,
        slippage_bps: int = 50,
    ) -> Dict[str, Any]:
        """Execute a token swap on a given chain using the configured DEX router.

        This currently supports EVM chains with Uniswap‑V2‑style routers and
        ERC‑20 -> ERC‑20 swaps. Native currency swaps (e.g. ETH -> token) are
        intentionally not handled here yet.
        """

        cfg = self.get_chain_config(chain)
        if not cfg:
            raise ValueError(f"Unknown chain: {chain}")
        if not cfg.get("is_evm", True):
            if chain.lower() == "solana":
                return await self._execute_swap_solana(
                    token_in, token_out, amount_in, slippage_bps, cfg
                )
            raise ValueError(
                f"DEX swap execution on {chain} is not available. "
                f"Supported: EVM chains (Ethereum, BSC, Polygon, Arbitrum, Optimism) and Solana."
            )

        router_info = self.dex_routers.get(chain)
        if not router_info:
            raise ValueError(f"No DEX router configured for chain {chain}. Add one via set_dex_router().")

        w3 = self._get_web3_for_chain(chain)
        if w3 is None:
            raise RuntimeError(f"Failed to create Web3 instance for chain {chain}")

        self._ensure_evm_wallet()
        from_addr = self._evm_address
        priv_hex = self._evm_private_key
        assert from_addr is not None and priv_hex is not None

        router_address = router_info["address"]
        if Web3 is not None:
            try:
                router_address = Web3.to_checksum_address(router_address)
                from_addr = Web3.to_checksum_address(from_addr)
            except Exception:
                pass

        # Minimal Uniswap V2 router ABI: getAmountsOut + swapExactTokensForTokens
        router_abi = [
            {
                "name": "getAmountsOut",
                "outputs": [{"name": "", "type": "uint256[]"}],
                "inputs": [
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "path", "type": "address[]"},
                ],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "name": "swapExactTokensForTokens",
                "outputs": [{"name": "", "type": "uint256[]"}],
                "inputs": [
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "amountOutMin", "type": "uint256"},
                    {"name": "path", "type": "address[]"},
                    {"name": "to", "type": "address"},
                    {"name": "deadline", "type": "uint256"},
                ],
                "stateMutability": "nonpayable",
                "type": "function",
            },
        ]
        router = w3.eth.contract(address=router_address, abi=router_abi)

        # Normalise token addresses and fetch decimals.
        if Web3 is not None:
            try:
                token_in = Web3.to_checksum_address(token_in)
                token_out = Web3.to_checksum_address(token_out)
            except Exception:
                pass

        in_contract = self._get_erc20_contract(w3, token_in)
        out_contract = self._get_erc20_contract(w3, token_out)

        decimals_in = int(in_contract.functions.decimals().call())
        decimals_out = int(out_contract.functions.decimals().call())

        amount_in_wei = int(Decimal(str(amount_in)) * (Decimal(10) ** decimals_in))
        path = [token_in, token_out]

        # Get expected output and compute minimum based on slippage.
        try:
            amounts = router.functions.getAmountsOut(amount_in_wei, path).call()
        except Exception as exc:
            raise RuntimeError(f"Router getAmountsOut failed on {chain}: {exc}") from exc

        if not isinstance(amounts, (list, tuple)) or len(amounts) < 2:
            raise RuntimeError("Unexpected router.getAmountsOut response")

        amount_out_wei = int(amounts[-1])
        min_out_wei = int(amount_out_wei * (1 - slippage_bps / 10_000))
        if min_out_wei <= 0:
            raise ValueError("Computed minimum output amount is non-positive")

        # Ensure router allowance for token_in.
        allowance = int(in_contract.functions.allowance(from_addr, router_address).call())
        approve_tx_hash: Optional[str] = None
        if allowance < amount_in_wei:
            nonce = w3.eth.get_transaction_count(from_addr)
            gas_price = w3.eth.gas_price
            approve_tx = in_contract.functions.approve(
                router_address,
                amount_in_wei,
            ).build_transaction(
                {
                    "from": from_addr,
                    "nonce": nonce,
                    "gasPrice": gas_price,
                    "chainId": cfg.get("chain_id") or w3.eth.chain_id,
                }
            )
            if "gas" not in approve_tx:
                approve_tx["gas"] = w3.eth.estimate_gas(approve_tx)

            account = Account.from_key(priv_hex)
            signed_approve = account.sign_transaction(approve_tx)
            tx_hash_bytes = w3.eth.send_raw_transaction(signed_approve.rawTransaction)
            approve_tx_hash = Web3.to_hex(tx_hash_bytes) if Web3 is not None else tx_hash_bytes.hex()
            # Wait for approval confirmation before swap.
            w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=600)

        # Build and send the swap transaction.
        nonce = w3.eth.get_transaction_count(from_addr)
        gas_price = w3.eth.gas_price
        deadline = int(time.time()) + 600  # 10 minutes from now

        swap_tx = router.functions.swapExactTokensForTokens(
            amount_in_wei,
            min_out_wei,
            path,
            from_addr,
            deadline,
        ).build_transaction(
            {
                "from": from_addr,
                "nonce": nonce,
                "gasPrice": gas_price,
                "chainId": cfg.get("chain_id") or w3.eth.chain_id,
            }
        )
        if "gas" not in swap_tx:
            swap_tx["gas"] = w3.eth.estimate_gas(swap_tx)

        account = Account.from_key(priv_hex)
        signed_swap = account.sign_transaction(swap_tx)
        swap_hash_bytes = w3.eth.send_raw_transaction(signed_swap.rawTransaction)
        swap_tx_hash = Web3.to_hex(swap_hash_bytes) if Web3 is not None else swap_hash_bytes.hex()
        receipt = w3.eth.wait_for_transaction_receipt(swap_hash_bytes, timeout=600)
        status_ok = bool(getattr(receipt, "status", receipt.get("status", 1)))  # type: ignore[arg-type]

        if self.event_bus:
            try:
                self.event_bus.publish(
                    "onchain.swap.executed",
                    {
                        "chain": chain,
                        "router": router_address,
                        "token_in": token_in,
                        "token_out": token_out,
                        "amount_in": float(amount_in),
                        "amount_out_wei": str(amount_out_wei),
                        "tx_hash": swap_tx_hash,
                        "status": "success" if status_ok else "failed",
                    },
                )
            except Exception:
                # Event bus is strictly best-effort here.
                pass

        return {
            "status": "success" if status_ok else "failed",
            "chain": chain,
            "router": router_address,
            "token_in": token_in,
            "token_out": token_out,
            "amount_in": float(amount_in),
            "amount_in_wei": str(amount_in_wei),
            "amount_out_wei": str(amount_out_wei),
            "min_amount_out_wei": str(min_out_wei),
            "tx_hash": swap_tx_hash,
            "approval_tx_hash": approve_tx_hash,
            "path": path,
        }


    async def _quote_swap_solana(self, token_in, token_out, amount_in, cfg):
        """Quote a Solana DEX swap via Jupiter Aggregator API."""
        import urllib.request, json as _json
        amount_lamports = int(float(amount_in) * 10**9)
        url = (
            f"https://quote-api.jup.ag/v6/quote?"
            f"inputMint={token_in}&outputMint={token_out}&amount={amount_lamports}&slippageBps=50"
        )
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            return {
                "chain": "solana", "amount_in": float(amount_in),
                "amount_out": int(data.get("outAmount", 0)) / 10**9,
                "price_impact_pct": float(data.get("priceImpactPct", 0)),
                "route_plan": data.get("routePlan", []),
            }
        except Exception as e:
            raise RuntimeError(f"Solana quote via Jupiter failed: {e}")

    async def _execute_swap_solana(self, token_in, token_out, amount_in, slippage_bps, cfg):
        """Execute a Solana DEX swap via Jupiter Aggregator API.

        Returns a quoted+prepared-swap payload. Final on-chain submission
        requires a Solana keypair; if none is attached we return the quote
        with a clear "needs_wallet" status instead of silently succeeding.
        """
        quote = await self._quote_swap_solana(token_in, token_out, amount_in, cfg)
        estimated_out = float(quote.get("amount_out", 0) or 0)
        slippage_frac = max(0.0, float(slippage_bps) / 10_000.0)
        min_amount_out = estimated_out * (1.0 - slippage_frac)
        has_key = bool(getattr(self, "_solana_private_key", None))
        return {
            "status": "quoted" if not has_key else "ready_to_submit",
            "chain": "solana",
            "token_in": token_in,
            "token_out": token_out,
            "amount_in": float(amount_in),
            "estimated_out": estimated_out,
            "min_amount_out": min_amount_out,
            "slippage_bps": int(slippage_bps),
            "price_impact_pct": quote.get("price_impact_pct", 0),
            "route_plan": quote.get("route_plan", []),
            "note": (
                "Jupiter swap prepared; submit with your Solana wallet."
                if not has_key
                else "Ready to submit via attached Solana keypair."
            ),
        }


__all__ = ["MultiChainTradeExecutor", "ChainStatus", "load_rpc_overrides_from_comprehensive_config"]
