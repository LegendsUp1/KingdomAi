#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI - Blockchain Connection Checker

This script checks the connectivity to configured blockchain networks
using the updated configuration files.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp
from dotenv import load_dotenv

# Add project root to path
project_root = str(Path(__file__).parent.parent.absolute())
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('blockchain_check.log')
    ]
)
logger = logging.getLogger(__name__)

class BlockchainChecker:
    def __init__(self):
        self.config_dir = Path(project_root) / 'config' / 'blockchain'
        self.session = None
        self.results = {}

    async def init_session(self):
        """Initialize aiohttp session."""
        self.session = aiohttp.ClientSession()

    async def close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()

    def load_config(self, chain: str) -> dict:
        """Load blockchain configuration from file."""
        config_file = self.config_dir / f"{chain.lower()}.json"
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found for {chain}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {config_file}")
            return {}

    async def check_rpc_connection(self, url: str, method: str = "eth_chainId", params: list = None) -> Tuple[bool, str]:
        """Check RPC connection with a simple request."""
        if not url:
            return False, "No URL provided"
            
        headers = {"Content-Type": "application/json"}
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": 1
        }
        
        try:
            async with self.session.post(url, json=payload, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'result' in data:
                        return True, f"Connected (Chain ID: {data.get('result')})"
                    return False, f"Unexpected response: {data.get('error', 'Unknown error')}"
                return False, f"HTTP {response.status}: {await response.text()}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    async def check_bitcoin(self):
        """Check Bitcoin connection."""
        config = self.load_config('bitcoin')
        if not config:
            return
            
        network = config.get('network', 'mainnet')
        endpoints = []
        
        # Add configured RPC URL if exists
        if 'rpc_url' in config.get(network, {}):
            endpoints.append((config[network]['rpc_url'], 'Configured RPC'))
        
        # Add public nodes
        for url in config.get('public_nodes', []):
            endpoints.append((url, 'Public Node'))
            
        # Check all endpoints
        results = []
        for url, source in endpoints:
            success, message = await self.check_rpc_connection(url, "getblockchaininfo", [])
            status = "✅" if success else "❌"
            results.append(f"{status} {source}: {url} - {message}")
            
        self.results['Bitcoin'] = results

    async def check_ethereum(self):
        """Check Ethereum connection."""
        config = self.load_config('ethereum')
        if not config:
            return
            
        network = config.get('network', 'mainnet')
        endpoints = []
        
        # Add configured RPC URL if exists
        if 'rpc_url' in config.get(network, {}):
            endpoints.append((config[network]['rpc_url'], 'Configured RPC'))
        
        # Add public nodes
        for url in config.get('public_nodes', []):
            endpoints.append((url, 'Public Node'))
            
        # Check all endpoints
        results = []
        for url, source in endpoints:
            success, message = await self.check_rpc_connection(url)
            status = "✅" if success else "❌"
            results.append(f"{status} {source}: {url} - {message}")
            
        self.results['Ethereum'] = results

    async def check_all(self):
        """Check all configured blockchains."""
        await self.init_session()
        
        try:
            # Check each blockchain
            await asyncio.gather(
                self.check_bitcoin(),
                self.check_ethereum(),
                # Add other blockchain checks here
            )
            
            # Print results
            print("\n=== Blockchain Connection Check Results ===\n")
            for chain, results in self.results.items():
                print(f"{chain}:")
                for result in results:
                    print(f"  {result}")
                print()
                
        finally:
            await self.close_session()

if __name__ == "__main__":
    checker = BlockchainChecker()
    asyncio.run(checker.check_all())
