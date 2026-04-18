#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API Key Broadcaster for Kingdom AI
Ensures ALL API keys are properly configured, displayed, and broadcast to all tabs and systems

This module ensures:
1. ALL API keys from api_key_manager are detected and displayed
2. Keys are broadcast to ALL tabs (Trading, Dashboard, Blockchain, etc.)
3. Keys are broadcast to ALL systems (Trading System, Mining System, etc.)
4. Real-time updates when keys are added/modified
5. Status tracking for each API key (configured/not configured)
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class APIKeyBroadcaster:
    """
    Broadcasts ALL API keys to all components of Kingdom AI
    
    Ensures complete system-wide integration of API credentials
    """
    
    def __init__(self, event_bus=None, api_key_manager=None):
        """
        Initialize API Key Broadcaster
        
        Args:
            event_bus: Event bus for broadcasting
            api_key_manager: API key manager instance
        """
        self.event_bus = event_bus
        self.api_key_manager = api_key_manager
        
        # Track broadcast status
        self.broadcast_count = 0
        self.last_broadcast = None
        
        # Track which components have received keys
        self.notified_components = set()
        
        # Categories of API keys
        self.categories = {
            'crypto_exchanges': [],
            'stock_exchanges': [],
            'forex_trading': [],
            'market_data': [],
            'blockchain_data': [],
            'ai_services': [],
            'cloud_services': [],
            'social_media': [],
            'fixed_income': [],
            'commodities': [],
            'derivatives': [],
            'alternative_investments': [],
            'esg_data': [],
            'financial_services': [],
            'news_media': [],
            'dev_tools': [],
            'analytics': [],
            'metaverse': []
        }
        
        # Status tracking for each key
        self.key_status = {}
        
        logger.info("✅ API Key Broadcaster initialized")
    
    async def broadcast_all_keys(self, force: bool = False):
        """
        Broadcast ALL API keys to all tabs and systems
        
        Args:
            force: Force broadcast even if recently done
        """
        try:
            logger.info("📢 Broadcasting ALL API keys to entire system...")
            
            if not self.api_key_manager:
                logger.error("API Key Manager not available")
                return False
            
            # 1. Get ALL API keys
            all_keys = self.api_key_manager.get_all_api_keys()
            
            # 2. Categorize keys
            categorized_keys = await self._categorize_keys(all_keys)
            
            # 3. Analyze key status
            key_status = await self._analyze_key_status(categorized_keys)
            
            # 4. Broadcast to ALL tabs
            await self._broadcast_to_all_tabs(categorized_keys, key_status)
            
            # 5. Broadcast to ALL systems
            await self._broadcast_to_all_systems(categorized_keys, key_status)
            
            # 6. Broadcast global summary
            await self._broadcast_global_summary(key_status)
            
            # 7. Update tracking
            self.broadcast_count += 1
            self.last_broadcast = datetime.now()
            self.key_status = key_status
            
            logger.info(f"✅ Broadcast complete: {len(key_status['configured'])} configured, "
                       f"{len(key_status['not_configured'])} not configured")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error broadcasting API keys: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _categorize_keys(self, all_keys: Dict) -> Dict[str, List[Dict]]:
        """Categorize all API keys by type"""
        try:
            categorized = {cat: [] for cat in self.categories.keys()}
            
            # Get category mappings from API key manager
            if hasattr(self.api_key_manager, 'CATEGORIES'):
                category_mappings = self.api_key_manager.CATEGORIES
            else:
                category_mappings = {}
            
            for service, key_data in all_keys.items():
                if not key_data or service.startswith('_'):
                    continue
                
                # Determine category
                service_lower = service.lower()
                found_category = None
                
                for category_name, services_in_category in category_mappings.items():
                    if service_lower in [s.lower() for s in services_in_category]:
                        found_category = category_name
                        break
                
                # Add to category
                if found_category and found_category in categorized:
                    categorized[found_category].append({
                        'service': service,
                        'data': key_data,
                        'category': found_category
                    })
            
            return categorized
            
        except Exception as e:
            logger.error(f"Error categorizing keys: {e}")
            return {cat: [] for cat in self.categories.keys()}
    
    async def _analyze_key_status(self, categorized_keys: Dict) -> Dict:
        """Analyze which keys are configured vs not configured"""
        try:
            status = {
                'configured': [],
                'not_configured': [],
                'partial': [],
                'by_category': {}
            }
            
            for category, keys in categorized_keys.items():
                category_status = {
                    'configured': 0,
                    'not_configured': 0,
                    'partial': 0
                }
                
                for key_info in keys:
                    service = key_info['service']
                    key_data = key_info['data']
                    
                    # Check if key is configured
                    is_configured = self._check_key_configured(key_data)
                    
                    if is_configured == 'full':
                        status['configured'].append(service)
                        category_status['configured'] += 1
                    elif is_configured == 'partial':
                        status['partial'].append(service)
                        category_status['partial'] += 1
                    else:
                        status['not_configured'].append(service)
                        category_status['not_configured'] += 1
                
                status['by_category'][category] = category_status
            
            # Calculate totals
            status['total'] = len(status['configured']) + len(status['partial']) + len(status['not_configured'])
            status['configured_percent'] = (len(status['configured']) / status['total'] * 100) if status['total'] > 0 else 0
            
            return status
            
        except Exception as e:
            logger.error(f"Error analyzing key status: {e}")
            return {'configured': [], 'not_configured': [], 'partial': []}
    
    def _check_key_configured(self, key_data: Any) -> str:
        """
        Check if a key is configured
        
        Returns:
            'full': Fully configured
            'partial': Partially configured
            'none': Not configured
        """
        if not key_data:
            return 'none'
        
        if isinstance(key_data, dict):
            # Check common key fields
            key_fields = ['api_key', 'api_secret', 'username', 'password', 
                         'client_id', 'client_secret', 'access_token', 
                         'api_key', 'secret_key']
            
            values = [key_data.get(field, '') for field in key_fields]
            non_empty = [v for v in values if v and str(v).strip() and str(v) != 'demo']
            
            if len(non_empty) == len([v for v in values if v is not None]):
                return 'full'
            elif len(non_empty) > 0:
                return 'partial'
            else:
                return 'none'
        elif isinstance(key_data, (list, str)):
            if key_data and str(key_data).strip() and str(key_data) != 'demo':
                return 'full'
        
        return 'none'
    
    async def _broadcast_to_all_tabs(self, categorized_keys: Dict, key_status: Dict):
        """Broadcast API keys to ALL GUI tabs"""
        try:
            if not self.event_bus:
                return
            
            tabs = [
                'trading_tab',
                'dashboard_tab',
                'blockchain_tab',
                'wallet_tab',
                'thoth_ai_tab',
                'api_key_manager_tab',
                'mining_tab',
                'settings_tab',
                'vr_tab',
                'code_generator_tab'
            ]
            
            for tab in tabs:
                try:
                    await self.event_bus.publish(f'api_keys.broadcast.{tab}', {
                        'categorized_keys': self._serialize_keys(categorized_keys),
                        'key_status': key_status,
                        'timestamp': datetime.now().isoformat(),
                        'broadcast_id': self.broadcast_count
                    })
                    self.notified_components.add(tab)
                    logger.debug(f"📢 Broadcast to {tab}")
                except Exception as e:
                    logger.error(f"Error broadcasting to {tab}: {e}")
            
            logger.info(f"✅ Broadcast to {len(tabs)} tabs")
            
        except Exception as e:
            logger.error(f"Error broadcasting to tabs: {e}")
    
    async def _broadcast_to_all_systems(self, categorized_keys: Dict, key_status: Dict):
        """Broadcast API keys to ALL backend systems"""
        try:
            if not self.event_bus:
                return
            
            systems = [
                'trading_system',
                'mining_system',
                'blockchain_system',
                'wallet_system',
                'thoth_ai_system',
                'ollama_brain',
                'quantum_ai_engine',
                'trading_coordinator',
                'autonomous_orchestrator',
                'risk_manager',
                'portfolio_manager',
                'signal_generator',
                'market_analyzer'
            ]
            
            for system in systems:
                try:
                    await self.event_bus.publish(f'api_keys.broadcast.{system}', {
                        'categorized_keys': self._serialize_keys(categorized_keys),
                        'key_status': key_status,
                        'timestamp': datetime.now().isoformat(),
                        'broadcast_id': self.broadcast_count
                    })
                    self.notified_components.add(system)
                    logger.debug(f"📢 Broadcast to {system}")
                except Exception as e:
                    logger.error(f"Error broadcasting to {system}: {e}")
            
            logger.info(f"✅ Broadcast to {len(systems)} backend systems")
            
        except Exception as e:
            logger.error(f"Error broadcasting to systems: {e}")
    
    async def _broadcast_global_summary(self, key_status: Dict):
        """Broadcast global summary to all components"""
        try:
            if not self.event_bus:
                return
            
            summary = {
                'total_keys': key_status.get('total', 0),
                'configured': len(key_status.get('configured', [])),
                'not_configured': len(key_status.get('not_configured', [])),
                'partial': len(key_status.get('partial', [])),
                'configured_percent': key_status.get('configured_percent', 0),
                'by_category': key_status.get('by_category', {}),
                'broadcast_count': self.broadcast_count,
                'last_broadcast': self.last_broadcast.isoformat() if self.last_broadcast else None,
                'notified_components': list(self.notified_components),
                'timestamp': datetime.now().isoformat()
            }
            
            # Broadcast to global channel
            await self.event_bus.publish('api_keys.global_summary', summary)
            
            # Also publish detailed lists
            await self.event_bus.publish('api_keys.configured_list', {
                'services': key_status.get('configured', []),
                'count': len(key_status.get('configured', []))
            })
            
            await self.event_bus.publish('api_keys.not_configured_list', {
                'services': key_status.get('not_configured', []),
                'count': len(key_status.get('not_configured', []))
            })
            
            logger.info(f"✅ Global summary broadcast: {summary['configured']}/{summary['total']} configured")
            
        except Exception as e:
            logger.error(f"Error broadcasting global summary: {e}")
    
    def _serialize_keys(self, categorized_keys: Dict) -> Dict:
        """Serialize keys for JSON transmission (remove sensitive data)"""
        try:
            serialized = {}
            
            for category, keys in categorized_keys.items():
                serialized[category] = []
                for key_info in keys:
                    # Only send service name and status, not actual keys
                    serialized[category].append({
                        'service': key_info['service'],
                        'configured': self._check_key_configured(key_info['data']),
                        'has_api_key': 'api_key' in key_info['data'] if isinstance(key_info['data'], dict) else False,
                        'has_api_secret': 'api_secret' in key_info['data'] if isinstance(key_info['data'], dict) else False
                    })
            
            return serialized
            
        except Exception as e:
            logger.error(f"Error serializing keys: {e}")
            return {}
    
    async def watch_for_changes(self):
        """Watch for API key changes and auto-broadcast"""
        try:
            logger.info("👁️ Watching for API key changes...")
            
            if not self.event_bus:
                return
            
            # Subscribe to API key change events
            await self.event_bus.subscribe('api.key.available.*', 
                                          self._handle_key_change)
            await self.event_bus.subscribe('api.key.updated.*',
                                          self._handle_key_change)
            
            logger.info("✅ Now watching for API key changes")
            
        except Exception as e:
            logger.error(f"Error setting up key watcher: {e}")
    
    async def _handle_key_change(self, event_data: Dict):
        """Handle API key change event"""
        try:
            logger.info(f"🔄 API key changed: {event_data.get('service')}")
            
            # Re-broadcast all keys
            await self.broadcast_all_keys(force=True)
            
        except Exception as e:
            logger.error(f"Error handling key change: {e}")
    
    def get_status(self) -> Dict:
        """Get broadcaster status"""
        return {
            'broadcast_count': self.broadcast_count,
            'last_broadcast': self.last_broadcast.isoformat() if self.last_broadcast else None,
            'notified_components': list(self.notified_components),
            'key_status': self.key_status,
            'is_watching': True
        }
    
    async def broadcast_to_specific_component(self, component: str):
        """Broadcast API keys to a specific component"""
        try:
            if not self.api_key_manager or not self.event_bus:
                return False
            
            # Get all keys
            all_keys = self.api_key_manager.get_all_api_keys()
            categorized_keys = await self._categorize_keys(all_keys)
            key_status = await self._analyze_key_status(categorized_keys)
            
            # Broadcast to specific component
            await self.event_bus.publish(f'api_keys.broadcast.{component}', {
                'categorized_keys': self._serialize_keys(categorized_keys),
                'key_status': key_status,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"✅ Broadcast to {component}")
            return True
            
        except Exception as e:
            logger.error(f"Error broadcasting to {component}: {e}")
            return False
