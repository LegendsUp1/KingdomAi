#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WhaleTracker component for monitoring large cryptocurrency transactions.
"""

import os
import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
import aiohttp

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

# SOTA 2026 FIX: Singleton instance to prevent multiple initializations
_whale_tracker_instance = None
_whale_tracker_lock = None

def get_whale_tracker(event_bus=None, config=None):
    """Get or create the singleton WhaleTracker instance."""
    global _whale_tracker_instance, _whale_tracker_lock
    import threading
    if _whale_tracker_lock is None:
        _whale_tracker_lock = threading.Lock()
    
    with _whale_tracker_lock:
        if _whale_tracker_instance is None:
            _whale_tracker_instance = WhaleTracker(event_bus=event_bus, config=config, _is_singleton=True)
        return _whale_tracker_instance

class WhaleTracker(BaseComponent):
    """
    Component for tracking large cryptocurrency transactions (whales).
    Monitors blockchain networks for significant movements of assets.
    
    SOTA 2026: Use get_whale_tracker() to get singleton instance.
    """
    
    def __init__(self, event_bus=None, config=None, _is_singleton=False):
        """
        Initialize the WhaleTracker component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
            _is_singleton: Internal flag - use get_whale_tracker() instead
        """
        global _whale_tracker_instance
        
        # SOTA 2026 FIX: If singleton exists and we're not creating it, return early
        if not _is_singleton and _whale_tracker_instance is not None:
            logger.debug("WhaleTracker singleton already exists - reusing")
            # Copy attributes from singleton
            self.__dict__.update(_whale_tracker_instance.__dict__)
            return
        
        super().__init__(name="WhaleTracker", event_bus=event_bus, config=config)
        self.name = "WhaleTracker"
        self.description = "Monitors large cryptocurrency transactions"
        
        # API configuration - check multiple sources for whale alert API key
        self.api_key = (
            self.config.get("whale_alert_api_key")
            or os.environ.get("WHALE_ALERT_API_KEY")
            or self._load_api_key_from_config()
            or ""
        )
        self.api_url = self.config.get("whale_alert_api_url", "https://api.whale-alert.io/v1")
        
        if not self.api_key:
            logger.info("Whale Alert API key not set - whale tracking will use on-chain analysis only. "
                       "Set WHALE_ALERT_API_KEY in .env or config/api_keys.json for live whale alerts.")
        
        # Tracking parameters
        self.min_value_usd = self.config.get("min_value_usd", 1000000)  # Minimum USD value to track (default: $1M)
        self.tracked_currencies = self.config.get("tracked_currencies", ["BTC", "ETH", "XRP", "BNB", "SOL", "USDT", "USDC"])
        self.update_interval = self.config.get("update_interval", 300)  # In seconds
        
        # Internal state
        self.session = None
        self.whale_transactions = []
        self.is_tracking = False
        self.tracking_task = None
        self.last_tracked_time = None
        self.exchanges = {}  # Mapping of exchange addresses
        self.known_wallets = {}  # Known wallet addresses
        self._session_closed = False  # SOTA 2026: Track session state for cleanup
        self._fully_initialized = False  # SOTA 2026: Prevent re-initialization
    
    def __del__(self):
        """SOTA 2026 FIX: Ensure aiohttp session is properly closed to prevent ResourceWarning."""
        if self.session and not self._session_closed:
            try:
                # Try to close session synchronously if possible
                if not self.session.closed:
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Schedule closure for later
                            loop.create_task(self._close_session_async())
                        else:
                            loop.run_until_complete(self._close_session_async())
                    except RuntimeError:
                        # No event loop available - session will be cleaned up by GC
                        pass
            except Exception as e:
                logger.warning("Error closing session in __del__: %s", e)
    
    async def _close_session_async(self):
        """Helper to close session asynchronously."""
        if self.session and not self.session.closed:
            await self.session.close()
            self._session_closed = True
        
    async def safe_publish(self, event_name, event_data=None):
        """Safely publish an event to the event bus with error handling.
        
        Args:
            event_name: The name of the event to publish
            event_data: The data to include with the event
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self.event_bus is None:
            logger.warning(f"Cannot publish event {event_name}: Event bus is None")
            return False
            
        try:
            self.event_bus.publish(event_name, event_data)
            return True
        except Exception as e:
            logger.error(f"Error publishing event {event_name}: {str(e)}")
            return False
    
    async def initialize(self):
        """Initialize the WhaleTracker component.
        
        Returns:
            bool: True if initialization was successful
        """
        # SOTA 2026 FIX: Prevent re-initialization
        if hasattr(self, '_fully_initialized') and self._fully_initialized:
            logger.debug("WhaleTracker already initialized - skipping")
            return True
        
        logger.info("Initializing WhaleTracker component")
        
        # Subscribe to relevant events
        if self.event_bus is not None:
            self.event_bus and self.event_bus.subscribe_sync("whale.tracking.start", self.on_tracking_start)
            self.event_bus and self.event_bus.subscribe_sync("whale.tracking.stop", self.on_tracking_stop)
            self.event_bus and self.event_bus.subscribe_sync("whale.config.update", self.on_config_update)
            self.event_bus and self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
        else:
            logger.warning("No event bus available, WhaleTracker will operate with limited functionality")
        
        # SOTA 2026 FIX: Close existing session before creating new one
        if self.session is not None and not self.session.closed:
            try:
                await self.session.close()
                self._session_closed = True
            except Exception as e:
                logger.warning("Error closing session in __del__: %s", e)
        
        # Create HTTP session with proper connector and timeout
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(limit=10, force_close=True)
        self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        self._session_closed = False
        
        # Load known exchanges and wallets
        await self.load_exchanges()
        await self.load_known_wallets()
        
        # Start tracking if auto-start is enabled
        if self.config.get("auto_start", True):
            await self.start_tracking()
        
        # SOTA 2026 FIX: Mark as fully initialized to prevent re-initialization
        self._fully_initialized = True
        logger.info("WhaleTracker component initialized")
        return True
        
    async def load_exchanges(self):
        """Load known exchange addresses."""
        exchanges_file = os.path.join(self.config.get("data_dir", "data"), "exchanges.json")
        
        try:
            if os.path.exists(exchanges_file):
                with open(exchanges_file, 'r') as f:
                    self.exchanges = json.load(f)
                logger.info(f"Loaded {len(self.exchanges)} exchange addresses")
            else:
                # Initialize with some known exchanges
                self.exchanges = {
                    "binance": {
                        "name": "Binance",
                        "addresses": {
                            "btc": ["3FGhvXARmcd3H9UPvQbcbYnLhXxV7JdfK5"],
                            "eth": ["0x28c6c06298d514db089934071355e5743bf21d60"]
                        }
                    },
                    "coinbase": {
                        "name": "Coinbase",
                        "addresses": {
                            "btc": ["13TRVwiqLMveg9aPAmZgcAix2J9RVJZNDC"],
                            "eth": ["0x503828976d22510aad0201ac7ec88293211d23da"]
                        }
                    }
                }
                # Save exchanges for future use
                await self.save_exchanges()
        except Exception as e:
            logger.error(f"Error loading exchanges: {str(e)}")
            self.exchanges = {}
    
    async def load_known_wallets(self):
        """Load known wallet addresses."""
        wallets_file = os.path.join(self.config.get("data_dir", "data"), "known_wallets.json")
        
        try:
            if os.path.exists(wallets_file):
                with open(wallets_file, 'r') as f:
                    self.known_wallets = json.load(f)
                logger.info(f"Loaded {len(self.known_wallets)} known wallets")
        except Exception as e:
            logger.error(f"Error loading known wallets: {str(e)}")
            self.known_wallets = {}
    
    async def save_exchanges(self):
        """Save exchange addresses to storage."""
        exchanges_file = os.path.join(self.config.get("data_dir", "data"), "exchanges.json")
        
        try:
            os.makedirs(os.path.dirname(exchanges_file), exist_ok=True)
            with open(exchanges_file, 'w') as f:
                json.dump(self.exchanges, f, indent=2)
            logger.info(f"Saved {len(self.exchanges)} exchange addresses")
        except Exception as e:
            logger.error(f"Error saving exchanges: {str(e)}")
    
    async def save_known_wallets(self):
        """Save known wallet addresses to storage."""
        wallets_file = os.path.join(self.config.get("data_dir", "data"), "known_wallets.json")
        
        try:
            os.makedirs(os.path.dirname(wallets_file), exist_ok=True)
            with open(wallets_file, 'w') as f:
                json.dump(self.known_wallets, f, indent=2)
            logger.info(f"Saved {len(self.known_wallets)} known wallets")
        except Exception as e:
            logger.error(f"Error saving known wallets: {str(e)}")
    
    async def start_tracking(self):
        """Start tracking whale transactions."""
        if self.is_tracking:
            logger.warning("Whale tracking is already active")
            return
        
        logger.info("Starting whale transaction tracking")
        self.is_tracking = True
        self.last_tracked_time = int(time.time()) - self.update_interval
        
        # Start tracking task
        if self.tracking_task is None or self.tracking_task.done():
            self.tracking_task = asyncio.create_task(self.track_transactions_loop())
        
        # Publish tracking status
        await self.safe_publish("whale.tracking.status", {
            "is_tracking": self.is_tracking,
            "transactions_count": len(self.whale_transactions),
            "last_update": self.last_tracked_time.isoformat() if isinstance(self.last_tracked_time, datetime) else None,
            "timestamp": datetime.now().isoformat()
        })
    
    async def stop_tracking(self):
        """Stop tracking whale transactions."""
        if not self.is_tracking:
            logger.warning("Whale tracking is not active")
            return
        
        logger.info("Stopping whale transaction tracking")
        self.is_tracking = False
        
        # Cancel tracking task
        if self.tracking_task and not self.tracking_task.done():
            self.tracking_task.cancel()
            try:
                await self.tracking_task
            except asyncio.CancelledError:
                pass
            self.tracking_task = None
        
        # Publish tracking status
        await self.safe_publish("whale.tracking.status", {
            "is_tracking": self.is_tracking,
            "transactions_count": len(self.whale_transactions),
            "last_update": self.last_tracked_time.isoformat() if isinstance(self.last_tracked_time, datetime) else None,
            "timestamp": datetime.now().isoformat()
        })
    
    async def track_transactions_loop(self):
        """Continuously track whale transactions at the specified interval."""
        try:
            while self.is_tracking:
                try:
                    await self.fetch_whale_transactions()
                except Exception as fetch_err:
                    logger.warning(f"Whale fetch error (will retry): {fetch_err}")
                try:
                    await asyncio.sleep(self.update_interval)
                except RuntimeError as loop_err:
                    # SOTA 2026 FIX: "no running event loop" - fall back to sync sleep
                    if not getattr(self, '_async_sleep_warned', False):
                        logger.warning(f"Async sleep failed ({loop_err}), using sync fallback")
                        self._async_sleep_warned = True
                    import time as _time
                    _time.sleep(self.update_interval)
        except asyncio.CancelledError:
            logger.info("Whale transaction tracking loop cancelled")
        except RuntimeError as e:
            if "no running event loop" in str(e).lower() or "no current event loop" in str(e).lower():
                logger.warning(f"Whale tracker: event loop unavailable, stopping gracefully: {e}")
            else:
                logger.error(f"Error in whale transaction tracking loop: {str(e)}")
            self.is_tracking = False
        except Exception as e:
            logger.error(f"Error in whale transaction tracking loop: {str(e)}")
            self.is_tracking = False
            
            # Restart tracking if configured to auto-restart
            if self.config.get("auto_restart", True):
                await asyncio.sleep(60)  # Wait before restarting
                await self.start_tracking()
    
    def _load_api_key_from_config(self):
        """Load whale alert API key from config/api_keys.json."""
        try:
            import json
            config_paths = [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'api_keys.json'),
                os.path.join(os.getcwd(), 'config', 'api_keys.json'),
            ]
            for config_path in config_paths:
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        data = json.load(f)
                    # Check _BLOCKCHAIN_DATA.whale_alert.api_key
                    whale_key = data.get('_BLOCKCHAIN_DATA', {}).get('whale_alert', {}).get('api_key', '')
                    if whale_key:
                        return whale_key
        except Exception as e:
            logger.warning("Error loading API key from config: %s", e)
        return None
    
    async def fetch_whale_transactions(self):
        """Fetch recent whale transactions from the API or blockchain explorers."""
        if not self.api_key:
            logger.debug("Whale Alert API key not configured, using blockchain explorers")
            # Fall back to real blockchain explorer APIs
            transactions = await self.fetch_whale_transactions_from_blockchain_explorers()
            if transactions:
                await self.process_transactions(transactions)
            # Update last tracked time even if no transactions found
            self.last_tracked_time = datetime.now()
            return
        
        current_time = int(time.time())
        
        try:
            start_time = int(self.last_tracked_time.timestamp()) if isinstance(self.last_tracked_time, datetime) else int((datetime.now() - timedelta(hours=24)).timestamp())
            end_time = int(datetime.now().timestamp())
            
            async with self.session.get(
                f"{self.api_url}/transactions",
                params={
                    "api_key": self.api_key if self.api_key else "",
                    "start": start_time,
                    "end": end_time,
                    "min_value": self.min_value_usd if self.min_value_usd else 1000000,
                    "cursor": ""
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    transactions = data.get("transactions", [])
                    
                    # Filter transactions by currency
                    filtered_transactions = [
                        tx for tx in transactions
                        if tx.get("symbol") in self.tracked_currencies
                    ]
                    
                    # Process transactions (always real data from API)
                    await self.process_transactions(filtered_transactions)
                    
                    logger.info(f"Fetched {len(filtered_transactions)} whale transactions")
                    
                else:
                    logger.error(f"Failed to fetch whale transactions. Status: {response.status}")
                    # Fall back to blockchain explorers if API fails
                    logger.info("Falling back to blockchain explorers")
                    transactions = await self.fetch_whale_transactions_from_blockchain_explorers()
                    if transactions:
                        await self.process_transactions(transactions)
        except Exception as e:
            logger.error(f"Error fetching whale transactions: {str(e)}")
            # Fall back to blockchain explorers if API call fails
            logger.info("Falling back to blockchain explorers")
            try:
                transactions = await self.fetch_whale_transactions_from_blockchain_explorers()
                if transactions:
                    await self.process_transactions(transactions)
            except Exception as fallback_err:
                logger.warning(f"Blockchain explorer fallback also failed: {fallback_err}")
        
        # Update last tracked time
        self.last_tracked_time = datetime.now()
    
    async def fetch_whale_transactions_from_blockchain_explorers(self):
        """Fetch real whale transactions from blockchain explorers when Whale Alert API is not available.
        
        Queries public blockchain explorer APIs for large transactions:
        - Bitcoin: Blockchain.com API for unconfirmed transactions
        - Ethereum: Etherscan public API (no key needed for basic queries)
        
        Returns:
            list: List of real whale transactions, or empty list if API calls fail
        """
        transactions = []
        
        try:
            # Fetch Bitcoin large transactions from Blockchain.com
            if "BTC" in self.tracked_currencies:
                try:
                    async with self.session.get(
                        "https://blockchain.info/unconfirmed-transactions?format=json",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            # Filter for large transactions (>= min_value_usd equivalent)
                            # Note: Blockchain.com API returns transactions in BTC, need to convert
                            # For simplicity, we'll look for transactions with significant BTC amounts
                            # Assuming BTC price ~$50k, $1M = ~20 BTC
                            min_btc = self.min_value_usd / 50000.0  # Approximate BTC threshold
                            
                            txs = data.get("txs", [])
                            for tx in txs[:10]:  # Limit to recent transactions
                                try:
                                    # Calculate total output value
                                    total_output = sum(
                                        float(out.get("value", 0) or 0) / 100000000.0  # Convert satoshi to BTC
                                        for out in tx.get("out", [])
                                    )
                                    
                                    if total_output >= min_btc:
                                        # Get addresses
                                        inputs = tx.get("inputs", [])
                                        outputs = tx.get("out", [])
                                        
                                        from_address = inputs[0].get("prev_out", {}).get("addr", "unknown") if inputs else "unknown"
                                        to_address = outputs[0].get("addr", "unknown") if outputs else "unknown"
                                        
                                        # Estimate USD value (approximate)
                                        amount_usd = total_output * 50000.0  # Approximate BTC price
                                        
                                        transaction = {
                                            "id": tx.get("hash", f"btc_{int(time.time())}"),
                                            "timestamp": tx.get("time", int(time.time())),
                                            "blockchain": "bitcoin",
                                            "symbol": "BTC",
                                            "from": {
                                                "address": from_address,
                                                "owner": "unknown",
                                                "owner_type": "unknown"
                                            },
                                            "to": {
                                                "address": to_address,
                                                "owner": "unknown",
                                                "owner_type": "unknown"
                                            },
                                            "amount": total_output,
                                            "amount_usd": amount_usd,
                                            "transaction_type": "transfer",
                                            "transaction_count": 1
                                        }
                                        transactions.append(transaction)
                                except Exception as tx_err:
                                    logger.debug(f"Error processing Bitcoin transaction: {tx_err}")
                                    continue
                except Exception as btc_err:
                    logger.debug(f"Error fetching Bitcoin transactions from Blockchain.com: {btc_err}")
            
            # Fetch Ethereum large transactions from Etherscan public API
            if "ETH" in self.tracked_currencies:
                try:
                    # Etherscan public API endpoint for large transactions
                    # Note: Free tier has rate limits, but basic queries work without API key
                    async with self.session.get(
                        "https://api.etherscan.io/api",
                        params={
                            "module": "proxy",
                            "action": "eth_getBlockByNumber",
                            "tag": "latest",
                            "boolean": "true",
                            "apikey": ""  # Public API doesn't require key for basic queries
                        },
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("status") == "1" and data.get("result"):
                                block = data.get("result", {})
                                txs = block.get("transactions", [])
                                
                                # Filter for large transactions
                                # Assuming ETH price ~$3000, $1M = ~333 ETH
                                min_eth = self.min_value_usd / 3000.0
                                
                                for tx in txs[:10]:  # Limit to recent transactions
                                    try:
                                        value_wei = int(tx.get("value", "0x0"), 16)
                                        value_eth = value_wei / 1e18
                                        
                                        if value_eth >= min_eth:
                                            from_address = tx.get("from", "unknown")
                                            to_address = tx.get("to", "unknown")
                                            amount_usd = value_eth * 3000.0  # Approximate ETH price
                                            
                                            transaction = {
                                                "id": tx.get("hash", f"eth_{int(time.time())}"),
                                                "timestamp": int(block.get("timestamp", "0x0"), 16),
                                                "blockchain": "ethereum",
                                                "symbol": "ETH",
                                                "from": {
                                                    "address": from_address,
                                                    "owner": "unknown",
                                                    "owner_type": "unknown"
                                                },
                                                "to": {
                                                    "address": to_address,
                                                    "owner": "unknown",
                                                    "owner_type": "unknown"
                                                },
                                                "amount": value_eth,
                                                "amount_usd": amount_usd,
                                                "transaction_type": "transfer",
                                                "transaction_count": 1
                                            }
                                            transactions.append(transaction)
                                    except Exception as tx_err:
                                        logger.debug(f"Error processing Ethereum transaction: {tx_err}")
                                        continue
                except Exception as eth_err:
                    logger.debug(f"Error fetching Ethereum transactions from Etherscan: {eth_err}")
            
            if transactions:
                logger.info(f"Fetched {len(transactions)} real whale transactions from blockchain explorers")
                return transactions
            else:
                logger.info("Awaiting real whale data from blockchain explorers - no large transactions found")
                return []
                
        except Exception as e:
            logger.warning(f"Error fetching whale transactions from blockchain explorers: {str(e)}")
            logger.info("Awaiting real whale data from blockchain explorers")
            return []
    
    async def process_transactions(self, transactions):
        """Process whale transactions from real blockchain data.
        
        Args:
            transactions: List of transaction data
        """
        for tx in transactions:
            tx["detected_at"] = datetime.now().isoformat()
            
            # Identify exchanges and known wallets
            from_address = tx.get("from", {}).get("address")
            to_address = tx.get("to", {}).get("address")
            
            # Lookup from address
            if from_address:
                tx["from"]["identified"] = self.identify_address(from_address, tx.get("symbol", "").lower())
                
            # Lookup to address
            if to_address:
                tx["to"]["identified"] = self.identify_address(to_address, tx.get("symbol", "").lower())
            
            # Determine transaction type
            if tx.get("from", {}).get("owner_type") == "exchange" and tx.get("to", {}).get("owner_type") != "exchange":
                tx["movement_type"] = "withdrawal_from_exchange"
            elif tx.get("from", {}).get("owner_type") != "exchange" and tx.get("to", {}).get("owner_type") == "exchange":
                tx["movement_type"] = "deposit_to_exchange"
            else:
                tx["movement_type"] = "wallet_to_wallet"
            
            # Calculate potential market impact
            symbol = tx.get("symbol", "")
            amount_usd = tx.get("amount_usd", 0)
            
            if symbol and amount_usd > 0:
                daily_volume = tx.get("daily_volume_usd", 0)
                market_cap = tx.get("market_cap_usd", 0)
                
                if daily_volume > 0:
                    volume_ratio = amount_usd / daily_volume
                    if volume_ratio > 0.05:
                        tx["market_impact"] = "critical"
                    elif volume_ratio > 0.01:
                        tx["market_impact"] = "high"
                    elif volume_ratio > 0.005:
                        tx["market_impact"] = "medium"
                    else:
                        tx["market_impact"] = "low"
                    tx["volume_ratio"] = round(volume_ratio, 6)
                elif market_cap > 0:
                    cap_ratio = amount_usd / market_cap
                    if cap_ratio > 0.01:
                        tx["market_impact"] = "critical"
                    elif cap_ratio > 0.001:
                        tx["market_impact"] = "high"
                    elif cap_ratio > 0.0001:
                        tx["market_impact"] = "medium"
                    else:
                        tx["market_impact"] = "low"
                    tx["market_cap_ratio"] = round(cap_ratio, 8)
                else:
                    if amount_usd > 50_000_000:
                        tx["market_impact"] = "high"
                    elif amount_usd > 10_000_000:
                        tx["market_impact"] = "medium"
                    else:
                        tx["market_impact"] = "low"
                    tx["market_impact_note"] = "estimated without volume/market-cap data"
            
            # Add to transaction history
            self.whale_transactions.append(tx)
            
            # Limit history size
            max_history = self.config.get("max_transaction_history", 1000)
            if len(self.whale_transactions) > max_history:
                self.whale_transactions = self.whale_transactions[-max_history:]
            
            # Publish whale alert
            await self.safe_publish("whale.transaction.detected", tx)

        # After processing a real batch, publish aggregated status for TradingTab
        if not simulated and transactions:
            try:
                preview = []
                for tx in transactions[:min(len(transactions), 10)]:
                    try:
                        symbol = tx.get("symbol", "").upper()
                        amount_native = float(tx.get("amount", 0) or 0)
                        amount_usd = float(tx.get("amount_usd", 0) or 0)
                        price = amount_usd / amount_native if amount_native > 0 else 0.0
                        ts_val = tx.get("timestamp", 0)
                        t_str = datetime.fromtimestamp(ts_val).strftime("%H:%M:%S") if ts_val else "N/A"

                        movement_type = tx.get("movement_type", "wallet_to_wallet")
                        if movement_type == "deposit_to_exchange":
                            side = "Buy"
                        elif movement_type == "withdrawal_from_exchange":
                            side = "Sell"
                        else:
                            side = "Move"

                        preview.append({
                            "symbol": symbol,
                            "side": side,
                            "amount": amount_native,
                            "price": price,
                            "time": t_str,
                        })
                    except Exception:
                        continue

                total_volume = 0.0
                for tx in transactions:
                    try:
                        if str(tx.get("symbol", "")).upper() == "BTC":
                            total_volume += float(tx.get("amount", 0) or 0)
                    except Exception:
                        continue

                payload = {
                    "message": "Whale tracking active (live data)",
                    "active": True,
                    "transactions": preview,
                    "total_volume": total_volume,
                    "whale_ratio": 0.0,
                }

                await self.safe_publish("trading.whale.status", payload)
            except Exception as e:
                logger.error(f"Error publishing trading.whale.status: {str(e)}")
    
    def identify_address(self, address, symbol):
        """
        Identify an address from known exchanges and wallets.
        
        Args:
            address: The blockchain address
            symbol: The cryptocurrency symbol (lowercase)
            
        Returns:
            dict: Identification information
        """
        # Check exchanges
        for exchange_id, exchange_data in self.exchanges.items():
            if symbol in exchange_data.get("addresses", {}):
                if address in exchange_data["addresses"][symbol]:
                    return {
                        "type": "exchange",
                        "name": exchange_data["name"],
                        "id": exchange_id
                    }
        
        # Check known wallets
        if address in self.known_wallets:
            wallet_data = self.known_wallets[address]
            return {
                "type": wallet_data.get("type", "known"),
                "name": wallet_data.get("name", "Unknown"),
                "id": wallet_data.get("id", address)
            }
        
        # Unknown address
        return {
            "type": "unknown",
            "name": "Unknown",
            "id": None
        }
    
    async def add_known_wallet(self, address, name, wallet_type="whale", notes=None):
        """
        Add a known wallet to the tracking database.
        
        Args:
            address: Wallet address
            name: Name or label for the wallet
            wallet_type: Type of wallet (e.g., "whale", "fund", "developer")
            notes: Additional notes about the wallet
            
        Returns:
            bool: Success status
        """
        try:
            self.known_wallets[address] = {
                "name": name,
                "type": wallet_type,
                "id": address,
                "notes": notes,
                "added_at": datetime.now().isoformat()
            }
            
            # Save updated wallets
            await self.save_known_wallets()
            
            logger.info(f"Added known wallet: {address} ({name})")
            return True
        except Exception as e:
            logger.error(f"Error adding known wallet: {str(e)}")
            return False
    
    async def update_tracking_config(self, config):
        """
        Update tracking configuration.
        
        Args:
            config: New configuration values
            
        Returns:
            dict: Updated configuration
        """
        # Configure the parameters
        if self.config is not None and "min_value_usd" in config:
            self.min_value_usd = config["min_value_usd"]
            
        if self.config is not None and "tracked_currencies" in config:
            self.tracked_currencies = config["tracked_currencies"]
            
        if self.config is not None and "update_interval" in config:
            self.update_interval = config["update_interval"]
        
        # Restart tracking if running
        was_tracking = self.is_tracking
        if was_tracking:
            await self.stop_tracking()
            await self.start_tracking()
        
        logger.info("Updated whale tracking configuration")
        
        return {
            "min_value_usd": self.min_value_usd,
            "tracked_currencies": self.tracked_currencies,
            "update_interval": self.update_interval,
            "is_tracking": self.is_tracking
        }
    
    async def get_recent_transactions(self, limit=10, currency=None, hours=24):
        """
        Get recent whale transactions.
        
        Args:
            limit: Maximum number of transactions to return
            currency: Filter by currency symbol
            hours: Get transactions from the last N hours
            
        Returns:
            list: Recent whale transactions
        """
        # Filter transactions by time
        cutoff_time = datetime.now() - timedelta(hours=hours)
        cutoff_timestamp = int(cutoff_time.timestamp())
        
        filtered_transactions = [
            tx for tx in self.whale_transactions
            if tx.get("timestamp", 0) >= cutoff_timestamp and
            (currency is None or tx.get("symbol") == currency)
        ]
        
        # Sort by timestamp (newest first)
        sorted_transactions = sorted(
            filtered_transactions,
            key=lambda tx: tx.get("timestamp", 0),
            reverse=True
        )
        
        # Limit the number of results
        return sorted_transactions[:limit]
    
    async def get_tracking_stats(self):
        """
        Get whale tracking statistics.
        
        Returns:
            dict: Tracking statistics
        """
        # Calculate basic statistics
        total_transactions = len(self.whale_transactions)
        
        # Get transactions from the last 24 hours
        last_24h_transactions = await self.get_recent_transactions(limit=1000, hours=24)
        
        # Calculate total volume by currency
        volume_by_currency = {}
        for tx in last_24h_transactions:
            symbol = tx.get("symbol")
            amount_usd = tx.get("amount_usd", 0)
            
            if symbol:
                if symbol not in volume_by_currency:
                    volume_by_currency[symbol] = 0
                volume_by_currency[symbol] += amount_usd
        
        # Calculate transaction types
        transaction_types = {}
        for tx in last_24h_transactions:
            movement_type = tx.get("movement_type", "unknown")
            
            if movement_type not in transaction_types:
                transaction_types[movement_type] = 0
            transaction_types[movement_type] += 1
        
        return {
            "is_tracking": self.is_tracking,
            "total_transactions_tracked": total_transactions,
            "transactions_last_24h": len(last_24h_transactions),
            "volume_by_currency_usd": volume_by_currency,
            "transaction_types": transaction_types,
            "min_value_usd": self.min_value_usd,
            "tracked_currencies": self.tracked_currencies,
            "update_interval": self.update_interval,
            "last_update": (
                (self.last_tracked_time.isoformat() if isinstance(self.last_tracked_time, datetime)
                 else datetime.fromtimestamp(self.last_tracked_time).isoformat())
                if self.last_tracked_time else None
            )
        }
    
    async def on_tracking_start(self, _):
        """Handle tracking start event."""
        await self.start_tracking()
    
    async def on_tracking_stop(self, _):
        """Handle tracking stop event."""
        await self.stop_tracking()
    
    async def on_config_update(self, data):
        """
        Handle config update event.
        
        Args:
            data: New configuration data
        """
        config = data.get("config", {})
        result = await self.update_tracking_config(config)
        
        # Publish config update result
        await self.safe_publish("whale.config.updated", {
            "request_id": data.get("request_id"),
            "config": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the WhaleTracker component."""
        logger.info("Shutting down WhaleTracker component")
        
        # Stop tracking
        if self.is_tracking:
            await self.stop_tracking()
        
        # Save data
        await self.save_known_wallets()
        
        # Close HTTP session
        if self.session and not self.session.closed:
            await self.session.close()
            self._session_closed = True
        
        logger.info("WhaleTracker component shut down successfully")
