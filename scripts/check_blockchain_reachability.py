#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Check reachability of all blockchains from kingdomweb3_v2.

This script uses core.multichain_trade_executor.MultiChainTradeExecutor to
iterate over every chain in COMPLETE_BLOCKCHAIN_NETWORKS and prints a concise
status report: reachable/unreachable, EVM/non-EVM, and (for EVM networks)
latest block height when available.

Usage (from project root):

    python scripts/check_blockchain_reachability.py

The script is read-only: it never sends transactions or modifies state. It
only performs RPC health checks.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import List

# Ensure project root (parent of scripts/) is on sys.path so that the top-level
# 'core' package can be imported when running this script as
#   python scripts/check_blockchain_reachability.py
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.multichain_trade_executor import (
    MultiChainTradeExecutor,
    load_rpc_overrides_from_comprehensive_config,
)


async def _check_all() -> int:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("check_blockchain_reachability")

    # Build per-chain RPC overrides from the comprehensive config so that
    # networks with multiple known endpoints automatically use the most
    # robust options (e.g. avoiding deprecated or auth-only RPC URLs).
    rpc_overrides = load_rpc_overrides_from_comprehensive_config()

    executor = MultiChainTradeExecutor(rpc_overrides=rpc_overrides)

    chains: List[str] = executor.get_supported_networks()
    logger.info("Checking reachability for %d chains...", len(chains))

    unreachable = 0

    for chain in chains:
        try:
            status = await executor.get_chain_status(chain)
        except Exception as exc:
            logger.error("%s: error during status check: %s", chain, exc)
            unreachable += 1
            continue

        line = f"{chain:20s} | EVM={status.is_evm!s:5s} | reachable={status.reachable!s:5s}"
        if status.is_evm and status.latest_block is not None:
            line += f" | latest_block={status.latest_block}"
        if status.error:
            line += f" | error={status.error}"

        if not status.reachable:
            unreachable += 1

        print(line)

    print("\nSummary: %d/%d chains reachable" % (len(chains) - unreachable, len(chains)))
    return 0 if unreachable == 0 else 1


def main() -> None:
    try:
        exit_code = asyncio.run(_check_all())
    except KeyboardInterrupt:
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    main()
