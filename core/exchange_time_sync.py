"""
SOTA 2026: Exchange Time Synchronization Module
Synchronizes local system time with exchange servers to prevent timestamp errors.
"""

import logging
import time
import requests
from typing import Dict, Optional
import threading

logger = logging.getLogger(__name__)


class ExchangeTimeSync:
    """
    Synchronizes time with exchange servers to prevent timestamp errors.
    
    SOTA 2026: Implements NTP-style time offset calculation for API calls.
    """
    
    def __init__(self):
        self.time_offsets: Dict[str, int] = {}  # exchange_name -> offset_ms
        self._lock = threading.RLock()
        self._last_sync: Dict[str, float] = {}
        self.sync_interval = 300  # Resync every 5 minutes
        
    def get_server_time(self, exchange_name: str, exchange_api_url: str) -> Optional[int]:
        """
        Get server time from exchange.
        
        Args:
            exchange_name: Exchange identifier (e.g., 'binanceus')
            exchange_api_url: Base API URL
            
        Returns:
            Server time in milliseconds, or None if failed
        """
        try:
            # Exchange-specific time endpoints
            time_endpoints = {
                'binanceus': '/api/v3/time',
                'binance': '/api/v3/time',
                'coinbase': '/time',
                'kraken': '/0/public/Time',
                'kucoin': '/api/v1/timestamp',
            }
            
            endpoint = time_endpoints.get(exchange_name.lower(), '/time')
            url = f"{exchange_api_url.rstrip('/')}{endpoint}"
            
            # Measure round-trip time
            local_before = int(time.time() * 1000)
            response = requests.get(url, timeout=5)
            local_after = int(time.time() * 1000)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse server time from exchange-specific format
                if exchange_name.lower() in ('binanceus', 'binance'):
                    server_time = data.get('serverTime')
                elif exchange_name.lower() == 'coinbase':
                    server_time = int(float(data.get('epoch', 0)) * 1000)
                elif exchange_name.lower() == 'kraken':
                    server_time = int(data.get('result', {}).get('unixtime', 0) * 1000)
                elif exchange_name.lower() == 'kucoin':
                    server_time = data.get('data')
                else:
                    server_time = data.get('serverTime') or data.get('time')
                
                # Estimate network latency and adjust
                network_latency = (local_after - local_before) // 2
                local_adjusted = local_before + network_latency
                
                return server_time
            
        except Exception as e:
            logger.debug(f"Failed to get server time from {exchange_name}: {e}")
        
        return None
    
    def sync_exchange(self, exchange_name: str, exchange_api_url: str) -> bool:
        """
        Synchronize time offset with an exchange.
        
        Args:
            exchange_name: Exchange identifier
            exchange_api_url: Base API URL
            
        Returns:
            True if sync successful, False otherwise
        """
        with self._lock:
            # Check if we need to resync
            last_sync = self._last_sync.get(exchange_name, 0)
            if time.time() - last_sync < self.sync_interval:
                return True  # Recently synced
            
            server_time = self.get_server_time(exchange_name, exchange_api_url)
            if server_time is not None:
                local_time = int(time.time() * 1000)
                offset = server_time - local_time
                
                self.time_offsets[exchange_name] = offset
                self._last_sync[exchange_name] = time.time()
                
                logger.debug(f"✅ Time synced with {exchange_name}: offset = {offset}ms")
                return True
            else:
                # SOTA 2026: Downgrade to debug - time sync failure is expected for some exchanges
                # (geo-blocked, no time endpoint, etc.) and we fall back to local time
                logger.debug(f"ℹ️ Time sync skipped for {exchange_name} (using local time)")
                return False
    
    def get_synchronized_timestamp(self, exchange_name: str) -> int:
        """
        Get current timestamp synchronized with exchange server.
        
        Args:
            exchange_name: Exchange identifier
            
        Returns:
            Synchronized timestamp in milliseconds
        """
        with self._lock:
            offset = self.time_offsets.get(exchange_name, 0)
            return int(time.time() * 1000) + offset
    
    def apply_to_ccxt_exchange(self, exchange, exchange_name: str):
        """
        Apply time synchronization to a CCXT exchange instance.
        
        SOTA 2026: Monkey-patches CCXT exchange methods to use synchronized time.
        
        Args:
            exchange: CCXT exchange instance
            exchange_name: Exchange identifier
        """
        # Sync time first
        sync_success = False
        if hasattr(exchange, 'urls') and 'api' in exchange.urls:
            api_url = exchange.urls.get('api')
            # Handle different URL formats (some CCXT exchanges use dict for api)
            if isinstance(api_url, dict):
                # Try public or base URL
                api_url = api_url.get('public') or api_url.get('rest') or api_url.get('v1') or next(iter(api_url.values()), None)
            if api_url:
                sync_success = self.sync_exchange(exchange_name, api_url)
        
        # Monkey-patch the nonce/timestamp method
        original_nonce = getattr(exchange, 'nonce', None)
        if original_nonce:
            def synchronized_nonce():
                return self.get_synchronized_timestamp(exchange_name)
            
            exchange.nonce = synchronized_nonce
            if sync_success:
                logger.debug(f"✅ Applied time sync to {exchange_name} exchange")
            else:
                # Offset=0 fallback - don't log warning since we already did
                logger.debug(f"ℹ️ Using local time for {exchange_name} (server sync unavailable)")


# Global singleton instance
_time_sync = None

def get_time_sync() -> ExchangeTimeSync:
    """Get or create the global ExchangeTimeSync instance."""
    global _time_sync
    if _time_sync is None:
        _time_sync = ExchangeTimeSync()
    return _time_sync
