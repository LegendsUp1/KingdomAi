#!/usr/bin/env python3
"""
Blockchain Data Sources for Kingdom AI Mining Operations.
Provides access to blockchain data for farming opportunities.
"""

import logging
import asyncio
import traceback
import json
import time
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class BlockchainDataSourcesMixin:
    """Mixin class providing access to blockchain data sources for mining intelligence."""
    
    def __init__(self):
        """Initialize blockchain data sources settings."""
        self.blockchain_data_sources = {}
        self.farming_opportunities = []
        self.data_source_status = {}
        self.last_scan_time = 0
        self.scan_interval = 300  # 5 minutes
    
    async def initialize_blockchain_data_sources(self) -> bool:
        """
        Initialize blockchain data sources for mining intelligence.
        
        Returns:
            bool: Success status
        """
        try:
            logger.info("Initializing blockchain data sources")
            
            # Get blockchain API keys immediately
            blockchain_api_keys = await self.load_api_keys_immediate([
                "ethereum_node", "bsc_node", "polygon_node", "avalanche_node", 
                "mining_pools", "mining_apis", "blockchain_apis"
            ])
            
            if not blockchain_api_keys:
                logger.warning("No blockchain API keys found, using default public endpoints")
            
            # Configure data sources
            self.blockchain_data_sources = {
                "ethereum": {
                    "name": "Ethereum",
                    "type": "blockchain",
                    "enabled": True,
                    "url": self._get_blockchain_url("ethereum_node", "https://eth-mainnet.public.blastapi.io"),
                    "connected": False,
                    "last_update": 0,
                    "farming_active": False
                },
                "binance_smart_chain": {
                    "name": "Binance Smart Chain",
                    "type": "blockchain",
                    "enabled": True,
                    "url": self._get_blockchain_url("bsc_node", "https://bsc-dataseed.binance.org"),
                    "connected": False,
                    "last_update": 0,
                    "farming_active": False
                },
                "mining_pools": {
                    "name": "Mining Pools API",
                    "type": "api",
                    "enabled": True,
                    "url": self._get_api_url("mining_pools", "https://api.miningpoolstats.stream/data"),
                    "connected": False,
                    "last_update": 0
                },
                "defi_protocols": {
                    "name": "DeFi Protocols",
                    "type": "api",
                    "enabled": True,
                    "url": self._get_api_url("defi_protocols", "https://api.llama.fi/protocols"),
                    "connected": False,
                    "last_update": 0
                }
            }
            
            # Initialize all data sources
            connection_tasks = []
            for source_id, source_config in self.blockchain_data_sources.items():
                if source_config["enabled"]:
                    task = asyncio.create_task(self._connect_data_source(source_id, source_config))
                    connection_tasks.append(task)
            
            # Wait for all connections with timeout
            try:
                await asyncio.wait_for(asyncio.gather(*connection_tasks, return_exceptions=True), timeout=10)
            except asyncio.TimeoutError:
                logger.warning("Some blockchain data source connections timed out")
            
            # Scan for farming opportunities
            await self.scan_farming_opportunities()
            
            # Schedule periodic scanning
            self._schedule_periodic_scanning()
            
            # Count connected sources
            connected_count = sum(1 for source in self.blockchain_data_sources.values() if source.get("connected", False))
            total_count = len(self.blockchain_data_sources)
            
            logger.info(f"Blockchain data sources initialized: {connected_count}/{total_count} connected")
            
            # Publish status
            if hasattr(self, 'safe_publish'):
                self.safe_publish("mining.blockchain_data.status", {
                    "status": "initialized",
                    "connected_sources": connected_count,
                    "total_sources": total_count,
                    "farming_opportunities": len(self.farming_opportunities)
                })
            
            return connected_count > 0
            
        except Exception as e:
            logger.error(f"Error initializing blockchain data sources: {e}")
            logger.error(traceback.format_exc())
            
            # Publish error
            if hasattr(self, 'safe_publish'):
                self.safe_publish("mining.blockchain_data.status", {
                    "status": "error",
                    "error": str(e)
                })
            
            return False
    
    def _get_blockchain_url(self, key_name: str, default_url: str) -> str:
        """
        Get blockchain node URL from API keys.
        
        Args:
            key_name: API key name
            default_url: Default URL to use if API key not found
            
        Returns:
            str: URL to use
        """
        if not hasattr(self, 'api_keys'):
            return default_url
            
        api_key_data = self.api_keys.get(key_name, {})
        return api_key_data.get("url", default_url)
    
    def _get_api_url(self, key_name: str, default_url: str) -> str:
        """
        Get API URL from API keys.
        
        Args:
            key_name: API key name
            default_url: Default URL to use if API key not found
            
        Returns:
            str: URL to use
        """
        if not hasattr(self, 'api_keys'):
            return default_url
            
        api_key_data = self.api_keys.get(key_name, {})
        
        # Check for different key formats
        if "url" in api_key_data:
            return api_key_data["url"]
        elif "endpoint" in api_key_data:
            return api_key_data["endpoint"]
        elif "base_url" in api_key_data:
            return api_key_data["base_url"]
            
        return default_url
    
    async def _connect_data_source(self, source_id: str, source_config: Dict[str, Any]) -> bool:
        """
        Connect to a blockchain data source.
        
        Args:
            source_id: Data source ID
            source_config: Data source configuration
            
        Returns:
            bool: Success status
        """
        try:
            logger.info(f"Connecting to {source_config['name']} data source")
            
            # Different connection methods based on source type
            if source_config["type"] == "blockchain":
                # For blockchain nodes, use Web3 if available
                if "web3_available" in globals() and web3_available:
                    try:
                        from web3 import Web3
                        provider_url = source_config["url"]
                        
                        if provider_url.startswith("wss://") or provider_url.startswith("ws://"):
                            provider = Web3.WebsocketProvider(provider_url)
                        else:
                            provider = Web3.HTTPProvider(provider_url)
                            
                        w3 = Web3(provider)
                        if w3.is_connected():
                            source_config["connected"] = True
                            source_config["web3"] = w3
                            source_config["last_update"] = time.time()
                            
                            # Get blockchain info
                            try:
                                source_config["chain_id"] = w3.eth.chain_id
                                source_config["latest_block"] = w3.eth.block_number
                                logger.info(f"Connected to {source_config['name']}: Chain ID {source_config['chain_id']}, Block {source_config['latest_block']}")
                            except Exception as e:
                                logger.warning(f"Connected to {source_config['name']} but could not get chain info: {e}")
                        else:
                            logger.warning(f"Failed to connect to {source_config['name']}")
                            source_config["connected"] = False
                    except Exception as e:
                        logger.warning(f"Error connecting to {source_config['name']} with Web3: {e}")
                        source_config["connected"] = False
                else:
                    logger.warning(f"Web3 not available, cannot connect to {source_config['name']}")
                    source_config["connected"] = False
                    
            elif source_config["type"] == "api":
                # For API sources, just check if the URL is accessible
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(source_config["url"], timeout=5) as response:
                            if response.status == 200:
                                source_config["connected"] = True
                                source_config["last_update"] = time.time()
                                logger.info(f"Connected to {source_config['name']} API")
                            else:
                                logger.warning(f"Failed to connect to {source_config['name']} API: Status {response.status}")
                                source_config["connected"] = False
                except Exception as e:
                    logger.warning(f"Error connecting to {source_config['name']} API: {e}")
                    source_config["connected"] = False
            
            # Update data source status
            self.data_source_status[source_id] = {
                "name": source_config["name"],
                "connected": source_config["connected"],
                "last_update": source_config.get("last_update", 0)
            }
            
            # Update UI if possible
            if hasattr(self, 'after') and self.after:
                self.after(0, self._update_data_source_status_ui)
            
            return source_config["connected"]
            
        except Exception as e:
            logger.error(f"Error connecting to data source {source_id}: {e}")
            logger.error(traceback.format_exc())
            
            # Update data source status
            self.data_source_status[source_id] = {
                "name": source_config.get("name", source_id),
                "connected": False,
                "error": str(e)
            }
            
            return False
    
    async def scan_farming_opportunities(self) -> List[Dict[str, Any]]:
        """
        Scan for farming opportunities across blockchains.
        
        Returns:
            List[Dict]: List of farming opportunities
        """
        try:
            logger.info("Scanning for farming opportunities")
            
            # Reset opportunities list
            self.farming_opportunities = []
            
            # Check if we have any connected data sources
            connected_sources = [s for s in self.blockchain_data_sources.values() if s.get("connected", False)]
            if not connected_sources:
                logger.warning("No connected blockchain data sources, cannot scan for farming opportunities")
                return []
            
            # Scan blockchain data sources for farming opportunities
            for source_id, source_config in self.blockchain_data_sources.items():
                if not source_config.get("connected", False):
                    continue
                    
                # Different scanning methods based on source type
                if source_config["type"] == "blockchain" and source_config.get("farming_active", False):
                    # For blockchain nodes, check for staking, farming, liquidity opportunities
                    await self._scan_blockchain_opportunities(source_id, source_config)
                    
                elif source_config["type"] == "api":
                    # For API sources, query for opportunities
                    await self._scan_api_opportunities(source_id, source_config)
            
            # Update UI if possible
            if hasattr(self, 'after') and self.after:
                self.after(0, self._update_farming_opportunities_ui)
            
            # Update last scan time
            self.last_scan_time = time.time()
            
            logger.info(f"Found {len(self.farming_opportunities)} farming opportunities")
            return self.farming_opportunities
            
        except Exception as e:
            logger.error(f"Error scanning for farming opportunities: {e}")
            logger.error(traceback.format_exc())
            return []
    
    async def _scan_blockchain_opportunities(self, source_id: str, source_config: Dict[str, Any]) -> None:
        """
        Scan a blockchain for farming opportunities via its Web3 connection.
        
        Args:
            source_id: Blockchain data source ID
            source_config: Blockchain data source configuration
        """
        try:
            logger.info(f"Scanning {source_config['name']} for farming opportunities")
            w3 = source_config.get("web3")
            
            if w3 and hasattr(w3, 'eth'):
                chain_id = source_config.get("chain_id", 0)
                latest_block = 0
                try:
                    latest_block = w3.eth.block_number
                    source_config["latest_block"] = latest_block
                except Exception as e:
                    logger.warning(f"Could not fetch latest block for {source_config['name']}: {e}")

                well_known_staking = {
                    "ethereum": [
                        {"contract": "0x00000000219ab540356cBB839Cbe05303d7705Fa", "name": "Ethereum 2.0 Beacon Deposit", "type": "staking", "token": "ETH", "min_stake": 32},
                    ],
                    "binance_smart_chain": [
                        {"contract": "0x0000000000000000000000000000000000001000", "name": "BSC Staking", "type": "staking", "token": "BNB", "min_stake": 1},
                    ],
                }

                for entry in well_known_staking.get(source_id, []):
                    try:
                        code = await asyncio.to_thread(w3.eth.get_code, w3.to_checksum_address(entry["contract"]))
                        contract_active = code and code != b'' and code != b'0x'
                    except Exception:
                        contract_active = False

                    balance_eth = 0.0
                    try:
                        balance_wei = await asyncio.to_thread(w3.eth.get_balance, w3.to_checksum_address(entry["contract"]))
                        balance_eth = float(w3.from_wei(balance_wei, 'ether'))
                    except Exception:
                        pass

                    self.farming_opportunities.append({
                        "id": f"{source_id}_{entry['name'].lower().replace(' ', '_')}",
                        "name": entry["name"],
                        "type": entry["type"],
                        "blockchain": source_config["name"],
                        "token": entry["token"],
                        "min_stake": entry.get("min_stake", 0),
                        "contract": entry["contract"],
                        "contract_active": contract_active,
                        "tvl_estimate": balance_eth,
                        "risk_level": "low" if contract_active else "unknown",
                        "latest_block": latest_block,
                        "scanned_at": time.time()
                    })
            else:
                logger.warning(f"No Web3 instance for {source_config['name']}, using static data")
                static_data = {
                    "ethereum": {"id": "eth_staking", "name": "Ethereum Staking", "type": "staking", "blockchain": "Ethereum", "apr": 4.2, "min_stake": 32, "token": "ETH", "risk_level": "low"},
                    "binance_smart_chain": {"id": "pancakeswap_farm", "name": "PancakeSwap Farming", "type": "yield_farming", "blockchain": "BSC", "apr": 12.5, "token_pair": "CAKE-BNB", "risk_level": "medium"},
                }
                if source_id in static_data:
                    self.farming_opportunities.append({**static_data[source_id], "scanned_at": time.time()})

            if hasattr(self, 'safe_publish'):
                self.safe_publish("mining.blockchain_scan.complete", {
                    "source_id": source_id,
                    "opportunities_found": len([o for o in self.farming_opportunities if o.get("blockchain") == source_config["name"]]),
                    "scanned_at": time.time()
                })

        except Exception as e:
            logger.error(f"Error scanning {source_config['name']} for opportunities: {e}")
            logger.error(traceback.format_exc())
    
    async def _scan_api_opportunities(self, source_id: str, source_config: Dict[str, Any]) -> None:
        """
        Scan an API endpoint for farming opportunities.
        
        Args:
            source_id: API data source ID
            source_config: API data source configuration
        """
        try:
            logger.info(f"Scanning {source_config['name']} API for farming opportunities")
            api_url = source_config.get("url", "")
            fetched = False

            if api_url:
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status == 200:
                                data = await response.json()
                                source_config["last_update"] = time.time()
                                fetched = True

                                if source_id == "defi_protocols" and isinstance(data, list):
                                    for protocol in data[:20]:
                                        name = protocol.get("name", "Unknown")
                                        tvl = protocol.get("tvl", 0)
                                        category = protocol.get("category", "unknown")
                                        chains = protocol.get("chains", [])
                                        if tvl and tvl > 1_000_000:
                                            self.farming_opportunities.append({
                                                "id": f"defi_{name.lower().replace(' ', '_')}",
                                                "name": name,
                                                "type": category if category in ("lending", "dexes", "yield") else "defi",
                                                "blockchain": ", ".join(chains[:3]) if chains else "Multiple",
                                                "tvl": tvl,
                                                "token": "Multiple",
                                                "risk_level": "low" if tvl > 100_000_000 else "medium",
                                                "scanned_at": time.time()
                                            })

                                elif source_id == "mining_pools" and isinstance(data, dict):
                                    pools = data.get("data", data.get("pools", []))
                                    if isinstance(pools, list):
                                        for pool in pools[:10]:
                                            pool_name = pool.get("name", pool.get("pool_id", "Unknown"))
                                            self.farming_opportunities.append({
                                                "id": f"pool_{pool_name.lower().replace(' ', '_')}",
                                                "name": pool_name,
                                                "type": "mining",
                                                "blockchain": pool.get("coin", "Multiple"),
                                                "hashrate": pool.get("hashrate", "N/A"),
                                                "workers": pool.get("workers", 0),
                                                "risk_level": "medium",
                                                "scanned_at": time.time()
                                            })
                            else:
                                logger.warning(f"API {source_config['name']} returned status {response.status}")
                except ImportError:
                    logger.warning("aiohttp not available for API scanning")
                except Exception as e:
                    logger.warning(f"Error fetching from {source_config['name']} API: {e}")

            if not fetched:
                logger.info(f"Using static fallback data for {source_config['name']}")
                static_fallbacks = {
                    "defi_protocols": [
                        {"id": "aave_lending", "name": "Aave Lending", "type": "lending", "blockchain": "Multiple", "apr": 3.8, "token": "Multiple", "risk_level": "low"},
                        {"id": "compound_lending", "name": "Compound Lending", "type": "lending", "blockchain": "Ethereum", "apr": 2.9, "token": "Multiple", "risk_level": "low"},
                    ],
                    "mining_pools": [
                        {"id": "ethermine_pool", "name": "Ethermine Pool", "type": "mining", "blockchain": "Ethereum", "estimated_reward": 0.05, "token": "ETH", "risk_level": "medium", "min_hashrate": "100 MH/s"},
                    ],
                }
                for opp in static_fallbacks.get(source_id, []):
                    self.farming_opportunities.append({**opp, "scanned_at": time.time(), "source": "static_fallback"})

            if hasattr(self, 'safe_publish'):
                self.safe_publish("mining.api_scan.complete", {
                    "source_id": source_id,
                    "fetched_live": fetched,
                    "opportunities_found": len([o for o in self.farming_opportunities if "scanned_at" in o]),
                    "scanned_at": time.time()
                })

        except Exception as e:
            logger.error(f"Error scanning {source_config['name']} API for opportunities: {e}")
            logger.error(traceback.format_exc())
    
    def _schedule_periodic_scanning(self) -> None:
        """
        Schedule periodic scanning for farming opportunities.
        """
        # Only available in Tkinter widgets
        if not hasattr(self, 'after') or not self.after:
            return
            
        async def run_scan():
            await self.scan_farming_opportunities()
            
        def schedule_next_scan():
            # Schedule next scan
            self.after(self.scan_interval * 1000, schedule_next_scan)
            # Run scan in an asyncio task
            asyncio.create_task(run_scan())
            
        # Schedule first scan
        self.after(self.scan_interval * 1000, schedule_next_scan)
        logger.info(f"Scheduled periodic farming opportunity scanning every {self.scan_interval} seconds")
