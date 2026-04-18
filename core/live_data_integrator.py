"""
Live Data Integrator - Integrates live system data into AI responses.

This module enables Kingdom AI to access real-time data from all system components
including trading, mining, blockchain, and wallet systems.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LiveDataIntegrator:
    """Integrates live system data into AI responses."""
    
    def __init__(self, event_bus, redis_client=None):
        """Initialize the Live Data Integrator.
        
        Args:
            event_bus: Event bus for component communication
            redis_client: Optional Redis client for caching
        """
        self.event_bus = event_bus
        self.redis = redis_client
        self.logger = logger
        self.data_cache = {}
        self.cache_timeout = 5  # Cache data for 5 seconds
        
    async def get_trading_data(self) -> dict:
        """Get current trading positions and market data.
        
        Returns:
            Dict with trading status, positions, and orders
        """
        try:
            # Check cache first
            if self._is_cache_valid('trading'):
                return self.data_cache['trading']['data']
            
            # Request trading data via event bus
            response = await self._publish_and_wait(
                'trading.get_full_status',
                {'include_positions': True, 'include_orders': True, 'include_balance': True},
                timeout=3.0
            )
            
            if response:
                self._update_cache('trading', response)
                self.logger.info("✅ Retrieved trading data")
                return response
            else:
                return {'status': 'unavailable', 'message': 'Trading data not available'}
                
        except Exception as e:
            self.logger.error(f"Error getting trading data: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def get_mining_data(self) -> dict:
        """Get current mining status and earnings.
        
        Returns:
            Dict with mining status, hashrate, and earnings
        """
        try:
            # Check cache first
            if self._is_cache_valid('mining'):
                return self.data_cache['mining']['data']
            
            # Request mining data via event bus
            response = await self._publish_and_wait(
                'mining.get_full_status',
                {'include_hashrate': True, 'include_earnings': True, 'include_pools': True},
                timeout=3.0
            )
            
            if response:
                self._update_cache('mining', response)
                self.logger.info("✅ Retrieved mining data")
                return response
            else:
                return {'status': 'unavailable', 'message': 'Mining data not available'}
                
        except Exception as e:
            self.logger.error(f"Error getting mining data: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def get_blockchain_data(self) -> dict:
        """Get blockchain network status.
        
        Returns:
            Dict with blockchain network information
        """
        try:
            # Check cache first
            if self._is_cache_valid('blockchain'):
                return self.data_cache['blockchain']['data']
            
            # Request blockchain data via event bus
            response = await self._publish_and_wait(
                'blockchain.get_all_networks',
                {'include_status': True, 'limit': 20},  # Get top 20 networks
                timeout=3.0
            )
            
            if response:
                self._update_cache('blockchain', response)
                self.logger.info("✅ Retrieved blockchain data")
                return response
            else:
                return {'status': 'unavailable', 'message': 'Blockchain data not available'}
                
        except Exception as e:
            self.logger.error(f"Error getting blockchain data: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def get_wallet_data(self) -> dict:
        """Get wallet balances across all chains.
        
        Returns:
            Dict with wallet balances and addresses
        """
        try:
            # Check cache first
            if self._is_cache_valid('wallet'):
                return self.data_cache['wallet']['data']
            
            # Request wallet data via event bus
            response = await self._publish_and_wait(
                'wallet.get_all_balances',
                {'include_addresses': True},
                timeout=3.0
            )
            
            if response:
                self._update_cache('wallet', response)
                self.logger.info("✅ Retrieved wallet data")
                return response
            else:
                return {'status': 'unavailable', 'message': 'Wallet data not available'}
                
        except Exception as e:
            self.logger.error(f"Error getting wallet data: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def get_system_health(self) -> dict:
        """Get overall system health status.
        
        Returns:
            Dict with system health metrics
        """
        try:
            # Request system health via event bus
            response = await self._publish_and_wait(
                'system.health.request',
                {},
                timeout=2.0
            )
            
            if response:
                self.logger.info("✅ Retrieved system health")
                return response
            else:
                return {'status': 'unavailable', 'message': 'System health data not available'}
                
        except Exception as e:
            self.logger.error(f"Error getting system health: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def query_data_for_question(self, question: str) -> dict:
        """Intelligently query relevant data based on user question.
        
        Args:
            question: User's question
            
        Returns:
            Dict with relevant live data
        """
        question_lower = question.lower()
        data = {}
        
        try:
            # Trading-related queries
            if any(word in question_lower for word in ['trade', 'trading', 'position', 'order', 'buy', 'sell', 'portfolio', 'balance']):
                self.logger.info("Fetching trading data for question")
                data['trading'] = await self.get_trading_data()
            
            # Mining-related queries
            if any(word in question_lower for word in ['mine', 'mining', 'hashrate', 'earning', 'pool', 'gpu']):
                self.logger.info("Fetching mining data for question")
                data['mining'] = await self.get_mining_data()
            
            # Blockchain-related queries
            if any(word in question_lower for word in ['blockchain', 'network', 'chain', 'block']):
                self.logger.info("Fetching blockchain data for question")
                data['blockchain'] = await self.get_blockchain_data()
            
            # Wallet-related queries
            if any(word in question_lower for word in ['wallet', 'balance', 'address', 'send', 'receive']):
                self.logger.info("Fetching wallet data for question")
                data['wallet'] = await self.get_wallet_data()
            
            # System status queries
            if any(word in question_lower for word in ['status', 'health', 'system', 'running', 'components']):
                self.logger.info("Fetching system health for question")
                data['system_health'] = await self.get_system_health()
            
            # If no specific keywords, get general system status
            if not data:
                self.logger.info("No specific keywords, fetching system health")
                data['system_health'] = await self.get_system_health()
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error querying data for question: {e}")
            return {'error': str(e)}
    
    async def _publish_and_wait(self, event: str, data: dict, timeout: float = 3.0) -> Optional[dict]:
        """Publish event and wait for response.
        
        Args:
            event: Event name to publish
            data: Event data
            timeout: Timeout in seconds
            
        Returns:
            Response data or None
        """
        try:
            response_event = f"{event}.response"
            response_data = None
            response_received = asyncio.Event()
            
            # Define response handler
            def handle_response(data):
                nonlocal response_data
                response_data = data
                response_received.set()
            
            # Subscribe to response
            self.event_bus.subscribe(response_event, handle_response)
            
            # Publish request
            self.event_bus.publish(event, data)
            
            # Wait for response with timeout
            try:
                await asyncio.wait_for(response_received.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout waiting for {response_event}")
                return None
            finally:
                # Unsubscribe
                try:
                    self.event_bus.unsubscribe(response_event, handle_response)
                except:
                    pass
            
            return response_data
            
        except Exception as e:
            self.logger.error(f"Error in publish_and_wait for {event}: {e}")
            return None
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid.
        
        Args:
            key: Cache key
            
        Returns:
            True if cache is valid
        """
        if key not in self.data_cache:
            return False
        
        cache_entry = self.data_cache[key]
        age = (datetime.now() - cache_entry['timestamp']).total_seconds()
        
        return age < self.cache_timeout
    
    def _update_cache(self, key: str, data: dict):
        """Update cache with new data.
        
        Args:
            key: Cache key
            data: Data to cache
        """
        self.data_cache[key] = {
            'data': data,
            'timestamp': datetime.now()
        }
    
    def format_live_data_for_ai(self, live_data: dict) -> str:
        """Format live data for inclusion in AI prompt.
        
        Args:
            live_data: Live data dict
            
        Returns:
            Formatted string for AI prompt
        """
        formatted = "\n\nLIVE SYSTEM DATA:\n"
        
        # Trading data
        if 'trading' in live_data and live_data['trading'].get('status') != 'error':
            trading = live_data['trading']
            formatted += "\nTRADING STATUS:\n"
            if 'positions' in trading:
                formatted += f"- Active Positions: {len(trading['positions'])}\n"
            if 'balance' in trading:
                formatted += f"- Portfolio Balance: ${trading['balance']}\n"
            if 'orders' in trading:
                formatted += f"- Open Orders: {len(trading['orders'])}\n"
        
        # Mining data
        if 'mining' in live_data and live_data['mining'].get('status') != 'error':
            mining = live_data['mining']
            formatted += "\nMINING STATUS:\n"
            if 'hashrate' in mining:
                formatted += f"- Current Hashrate: {mining['hashrate']} MH/s\n"
            if 'earnings' in mining:
                formatted += f"- Daily Earnings: ${mining['earnings']}\n"
            if 'pools' in mining:
                formatted += f"- Active Pools: {len(mining['pools'])}\n"
        
        # Blockchain data
        if 'blockchain' in live_data and live_data['blockchain'].get('status') != 'error':
            blockchain = live_data['blockchain']
            formatted += "\nBLOCKCHAIN NETWORKS:\n"
            if 'networks' in blockchain:
                formatted += f"- Total Networks: {len(blockchain['networks'])}\n"
                online = sum(1 for n in blockchain['networks'] if n.get('status') == 'online')
                formatted += f"- Networks Online: {online}\n"
        
        # Wallet data
        if 'wallet' in live_data and live_data['wallet'].get('status') != 'error':
            wallet = live_data['wallet']
            formatted += "\nWALLET STATUS:\n"
            if 'balances' in wallet:
                formatted += f"- Chains with Balance: {len(wallet['balances'])}\n"
            if 'total_value' in wallet:
                formatted += f"- Total Value: ${wallet['total_value']}\n"
        
        # System health
        if 'system_health' in live_data and live_data['system_health'].get('status') != 'error':
            health = live_data['system_health']
            formatted += "\nSYSTEM HEALTH:\n"
            if 'components' in health:
                formatted += f"- Active Components: {len(health['components'])}\n"
            if 'uptime' in health:
                formatted += f"- Uptime: {health['uptime']}\n"
        
        return formatted
