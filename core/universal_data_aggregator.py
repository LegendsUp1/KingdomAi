#!/usr/bin/env python3
"""
Kingdom AI - Universal Data Aggregator
Aggregates ANY data from ALL system components for BookTok/visual generation.
Works with trading, mining, wallet, blockchain, books, VR, code, AI, and any future data sources.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Callable
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger("KingdomAI.UniversalDataAggregator")

@dataclass
class DataSource:
    """Represents a registered data source in the system."""
    name: str
    category: str  # trading, mining, wallet, blockchain, books, vr, code, ai, custom
    event_patterns: List[str]  # Event bus patterns to subscribe to
    data_extractor: Optional[Callable] = None  # Custom data extraction function
    priority: int = 5  # 1-10, higher = more important for visualization
    visualization_hints: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

@dataclass
class DataVisualization:
    """Represents a visualization template for a data type."""
    name: str
    data_types: List[str]  # Which data types this visualization supports
    render_function: str  # Name of the rendering method
    priority: int = 5
    requires_fields: List[str] = field(default_factory=list)  # Required data fields

class UniversalDataAggregator:
    """Universal aggregator that works with ANY data from ALL system components."""
    
    def __init__(self, event_bus=None):
        """Initialize the Universal Data Aggregator.
        
        Args:
            event_bus: System event bus for subscribing to all data streams
        """
        self.event_bus = event_bus
        self.logger = logger
        
        # Registry of all data sources
        self.data_sources: Dict[str, DataSource] = {}
        
        # Live data snapshots from ALL sources
        self.data_snapshots: Dict[str, Any] = {}
        
        # Visualization templates registry
        self.visualizations: Dict[str, DataVisualization] = {}
        
        # Statistics tracking
        self.stats = {
            'total_events_received': 0,
            'active_sources': 0,
            'last_update': None,
            'data_freshness': {}
        }
        
        # Initialize with default data sources
        self._register_default_sources()
        self._register_default_visualizations()
        
        # Subscribe to events
        if self.event_bus:
            self._subscribe_to_all_events()
    
    def _register_default_sources(self):
        """Register all known system data sources."""
        
        # Trading data sources
        self.register_source(DataSource(
            name='trading_portfolio',
            category='trading',
            event_patterns=['trading.portfolio.snapshot', 'trading.portfolio.*'],
            priority=9,
            visualization_hints={'type': 'financial', 'color': 'green'}
        ))
        
        self.register_source(DataSource(
            name='trading_prices',
            category='trading',
            event_patterns=['trading.live_prices', 'trading.price.*'],
            priority=8,
            visualization_hints={'type': 'chart', 'animated': True}
        ))
        
        self.register_source(DataSource(
            name='trading_risk',
            category='trading',
            event_patterns=['trading.risk.snapshot', 'trading.risk.*'],
            priority=7,
            visualization_hints={'type': 'gauge', 'color': 'red'}
        ))
        
        self.register_source(DataSource(
            name='trading_ai',
            category='trading',
            event_patterns=['trading.ai.snapshot', 'trading.strategy.*'],
            priority=8,
            visualization_hints={'type': 'list', 'icon': '🤖'}
        ))
        
        # Mining data sources
        self.register_source(DataSource(
            name='mining_status',
            category='mining',
            event_patterns=['mining.status', 'mining.*.status'],
            priority=8,
            visualization_hints={'type': 'stats', 'icon': '⛏️'}
        ))
        
        self.register_source(DataSource(
            name='mining_analytics',
            category='mining',
            event_patterns=['analytics.mining.*', 'mining.coin_analytics'],
            priority=7,
            visualization_hints={'type': 'chart', 'color': 'orange'}
        ))
        
        # Wallet data sources
        self.register_source(DataSource(
            name='wallet_balance',
            category='wallet',
            event_patterns=['wallet.balance.update', 'wallet.*.balance'],
            priority=9,
            visualization_hints={'type': 'financial', 'icon': '💰'}
        ))
        
        self.register_source(DataSource(
            name='wallet_transactions',
            category='wallet',
            event_patterns=['wallet.transaction.*', 'blockchain.transaction_recorded'],
            priority=6,
            visualization_hints={'type': 'list', 'scrolling': True}
        ))
        
        # Blockchain data sources
        self.register_source(DataSource(
            name='blockchain_performance',
            category='blockchain',
            event_patterns=['blockchain.performance_update', 'blockchain.*.performance'],
            priority=7,
            visualization_hints={'type': 'network_graph'}
        ))
        
        self.register_source(DataSource(
            name='blockchain_contracts',
            category='blockchain',
            event_patterns=['blockchain.contract_interaction', 'blockchain.contract.*'],
            priority=6,
            visualization_hints={'type': 'code', 'icon': '📜'}
        ))
        
        # Learning/AI data sources
        self.register_source(DataSource(
            name='learning_metrics',
            category='ai',
            event_patterns=['learning.metrics', 'learning.*'],
            priority=8,
            visualization_hints={'type': 'progress', 'color': 'blue'}
        ))
        
        self.register_source(DataSource(
            name='learning_readiness',
            category='ai',
            event_patterns=['learning.readiness', 'learning.state.*'],
            priority=9,
            visualization_hints={'type': 'status', 'animated': True}
        ))
        
        self.register_source(DataSource(
            name='ai_responses',
            category='ai',
            event_patterns=['ai.response', 'ai.query', 'brain.*'],
            priority=7,
            visualization_hints={'type': 'chat', 'icon': '🧠'}
        ))
        
        # Book data sources
        self.register_source(DataSource(
            name='book_data',
            category='books',
            event_patterns=['book.data.ready', 'book.*'],
            priority=8,
            visualization_hints={'type': 'media', 'icon': '📚'}
        ))
        
        self.register_source(DataSource(
            name='book_library',
            category='books',
            event_patterns=['book.library.update', 'book.library.*'],
            priority=7,
            visualization_hints={'type': 'grid', 'icon': '📖'}
        ))
        
        # VR data sources
        self.register_source(DataSource(
            name='vr_status',
            category='vr',
            event_patterns=['vr.status', 'vr.*'],
            priority=6,
            visualization_hints={'type': '3d', 'icon': '🥽'}
        ))
        
        # Code generation sources
        self.register_source(DataSource(
            name='code_generated',
            category='code',
            event_patterns=['code.generated', 'code.*'],
            priority=6,
            visualization_hints={'type': 'code', 'syntax': 'python'}
        ))
        
        # API Keys sources
        self.register_source(DataSource(
            name='api_keys',
            category='system',
            event_patterns=['api_keys.loaded', 'api_keys.*'],
            priority=5,
            visualization_hints={'type': 'list', 'masked': True}
        ))
        
        # Memory/Database sources
        self.register_source(DataSource(
            name='memory_update',
            category='system',
            event_patterns=['memory.update', 'memory.*'],
            priority=6,
            visualization_hints={'type': 'timeline'}
        ))
        
        # Sentience/Consciousness sources
        self.register_source(DataSource(
            name='sentience',
            category='ai',
            event_patterns=['sentience.*', 'consciousness.*'],
            priority=8,
            visualization_hints={'type': 'gauge', 'color': 'purple', 'animated': True}
        ))
        
        # Knowledge sources (dictionary, encyclopedia, learned data)
        self.register_source(DataSource(
            name='knowledge_dictionary',
            category='knowledge',
            event_patterns=['knowledge.dictionary.*', 'knowledge.definition.*'],
            priority=7,
            visualization_hints={'type': 'text', 'icon': '📖'}
        ))
        
        self.register_source(DataSource(
            name='knowledge_encyclopedia',
            category='knowledge',
            event_patterns=['knowledge.encyclopedia.*', 'knowledge.wikipedia.*'],
            priority=7,
            visualization_hints={'type': 'text', 'icon': '📚'}
        ))
        
        self.register_source(DataSource(
            name='knowledge_learned',
            category='knowledge',
            event_patterns=['knowledge.learned.*', 'learning.insight', 'learning.pattern'],
            priority=8,
            visualization_hints={'type': 'timeline', 'icon': '🧠'}
        ))
        
        self.register_source(DataSource(
            name='knowledge_aggregated',
            category='knowledge',
            event_patterns=['knowledge.aggregated', 'knowledge.request'],
            priority=9,
            visualization_hints={'type': 'text', 'icon': '🔍'}
        ))
        
        logger.info(f"✅ Registered {len(self.data_sources)} default data sources")
    
    def _register_default_visualizations(self):
        """Register default visualization templates."""
        
        self.register_visualization(DataVisualization(
            name='financial_display',
            data_types=['trading', 'wallet', 'financial'],
            render_function='_render_financial_data',
            priority=9,
            requires_fields=['value', 'currency']
        ))
        
        self.register_visualization(DataVisualization(
            name='chart_display',
            data_types=['trading', 'mining', 'analytics'],
            render_function='_render_chart_data',
            priority=8,
            requires_fields=['data_points']
        ))
        
        self.register_visualization(DataVisualization(
            name='stats_display',
            data_types=['mining', 'system', 'performance'],
            render_function='_render_stats_data',
            priority=7,
            requires_fields=['metrics']
        ))
        
        self.register_visualization(DataVisualization(
            name='list_display',
            data_types=['transactions', 'items', 'list'],
            render_function='_render_list_data',
            priority=6,
            requires_fields=['items']
        ))
        
        self.register_visualization(DataVisualization(
            name='media_display',
            data_types=['books', 'images', 'media'],
            render_function='_render_media_data',
            priority=8,
            requires_fields=['title', 'content']
        ))
        
        self.register_visualization(DataVisualization(
            name='code_display',
            data_types=['code', 'contracts', 'text'],
            render_function='_render_code_data',
            priority=6,
            requires_fields=['code']
        ))
        
        self.register_visualization(DataVisualization(
            name='status_display',
            data_types=['ai', 'system', 'status'],
            render_function='_render_status_data',
            priority=7,
            requires_fields=['status']
        ))
        
        self.register_visualization(DataVisualization(
            name='network_display',
            data_types=['blockchain', 'network', 'graph'],
            render_function='_render_network_data',
            priority=7,
            requires_fields=['nodes']
        ))
        
        logger.info(f"✅ Registered {len(self.visualizations)} visualization templates")
    
    def register_source(self, source: DataSource):
        """Register a new data source dynamically.
        
        Args:
            source: DataSource configuration
        """
        self.data_sources[source.name] = source
        self.data_snapshots[source.name] = {
            'data': None,
            'last_update': None,
            'event_count': 0
        }
        logger.debug(f"Registered data source: {source.name} ({source.category})")
    
    def register_visualization(self, viz: DataVisualization):
        """Register a new visualization template.
        
        Args:
            viz: DataVisualization configuration
        """
        self.visualizations[viz.name] = viz
        logger.debug(f"Registered visualization: {viz.name}")
    
    def _subscribe_to_all_events(self):
        """Subscribe to ALL registered data source events."""
        subscribed_patterns = set()
        
        for source in self.data_sources.values():
            if not source.enabled:
                continue
            
            for pattern in source.event_patterns:
                if pattern not in subscribed_patterns:
                    # Subscribe to this event pattern
                    # CRITICAL FIX: Lambda must accept single 'data' parameter from event bus
                    self.event_bus.subscribe_sync(pattern, 
                        lambda data, src=source: self._on_data_event(pattern, data, src))
                    subscribed_patterns.add(pattern)
        
        logger.info(f"✅ Subscribed to {len(subscribed_patterns)} event patterns from {len(self.data_sources)} sources")
    
    def _on_data_event(self, event_type: str, data: Dict[str, Any], source: DataSource):
        """Universal event handler for ALL data events.
        
        Args:
            event_type: Event type string
            data: Event data
            source: Source that triggered this event
        """
        # Update snapshot
        self.data_snapshots[source.name] = {
            'data': data,
            'last_update': time.time(),
            'event_count': self.data_snapshots[source.name]['event_count'] + 1,
            'event_type': event_type,
            'category': source.category
        }
        
        # Update statistics
        self.stats['total_events_received'] += 1
        self.stats['last_update'] = datetime.now().isoformat()
        self.stats['data_freshness'][source.name] = time.time()
        
        # Count active sources (updated in last 5 minutes)
        cutoff = time.time() - 300
        self.stats['active_sources'] = sum(
            1 for ts in self.stats['data_freshness'].values() if ts > cutoff
        )
        
        logger.debug(f"Data event: {event_type} from {source.name} ({source.category})")
    
    async def aggregate_all_data(self, prompt: str = "", filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Aggregate ALL available data from ALL sources.
        
        Args:
            prompt: User prompt to guide data selection
            filters: Optional filters (categories, priorities, freshness)
            
        Returns:
            Complete aggregated data context
        """
        filters = filters or {}
        
        context = {
            'timestamp': datetime.now().isoformat(),
            'prompt': prompt,
            'data_by_category': {},
            'data_by_source': {},
            'highlights': [],
            'statistics': self.stats.copy(),
            'visualization_suggestions': []
        }
        
        # Filter by category if specified
        allowed_categories = filters.get('categories', None)
        min_priority = filters.get('min_priority', 0)
        max_age_seconds = filters.get('max_age_seconds', 3600)
        
        cutoff_time = time.time() - max_age_seconds
        
        # Aggregate data from all sources
        for source_name, source in self.data_sources.items():
            if not source.enabled:
                continue
            
            # Apply filters
            if allowed_categories and source.category not in allowed_categories:
                continue
            
            if source.priority < min_priority:
                continue
            
            snapshot = self.data_snapshots.get(source_name, {})
            last_update = snapshot.get('last_update')
            
            # Check freshness
            if last_update and last_update < cutoff_time:
                continue
            
            data = snapshot.get('data')
            if data is None:
                continue
            
            # Add to category grouping
            if source.category not in context['data_by_category']:
                context['data_by_category'][source.category] = {}
            
            context['data_by_category'][source.category][source_name] = {
                'data': data,
                'priority': source.priority,
                'last_update': last_update,
                'visualization_hints': source.visualization_hints
            }
            
            # Add to source mapping
            context['data_by_source'][source_name] = {
                'category': source.category,
                'data': data,
                'priority': source.priority
            }
            
            # Generate highlights based on priority and data
            if source.priority >= 8:
                highlight = self._generate_highlight(source, data)
                if highlight:
                    context['highlights'].append(highlight)
        
        # Sort highlights by importance
        context['highlights'] = sorted(
            context['highlights'],
            key=lambda x: x.get('priority', 0),
            reverse=True
        )[:10]  # Top 10 highlights
        
        # Suggest visualizations based on available data
        context['visualization_suggestions'] = self._suggest_visualizations(context)
        
        return context
    
    def _generate_highlight(self, source: DataSource, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate a highlight from data source.
        
        Args:
            source: Data source
            data: Source data
            
        Returns:
            Highlight dictionary or None
        """
        try:
            # Category-specific highlight generation
            if source.category == 'trading':
                if 'daily_pnl' in data:
                    pnl = data['daily_pnl']
                    if abs(pnl) > 100:
                        return {
                            'text': f"📈 Trading P&L: ${pnl:+,.2f}",
                            'priority': 9,
                            'category': 'trading',
                            'icon': '📈' if pnl > 0 else '📉'
                        }
                
                if 'total_value' in data:
                    value = data['total_value']
                    if value > 1000:
                        return {
                            'text': f"💼 Portfolio: ${value:,.2f}",
                            'priority': 8,
                            'category': 'trading'
                        }
            
            elif source.category == 'mining':
                if 'daily_revenue' in data:
                    revenue = data['daily_revenue']
                    if revenue > 10:
                        return {
                            'text': f"⛏️ Mining Revenue: ${revenue:,.2f}/day",
                            'priority': 8,
                            'category': 'mining'
                        }
            
            elif source.category == 'wallet':
                if 'total_balance_usd' in data:
                    balance = data['total_balance_usd']
                    if balance > 100:
                        return {
                            'text': f"💰 Wallet Balance: ${balance:,.2f}",
                            'priority': 9,
                            'category': 'wallet'
                        }
            
            elif source.category == 'ai':
                if 'predator_mode_active' in data and data['predator_mode_active']:
                    return {
                        'text': "🦁 PREDATOR MODE ACTIVE",
                        'priority': 10,
                        'category': 'ai',
                        'icon': '🦁'
                    }
                
                if 'state' in data:
                    return {
                        'text': f"🧠 AI State: {data['state']}",
                        'priority': 7,
                        'category': 'ai'
                    }
            
            elif source.category == 'books':
                if 'featured_book' in data and data['featured_book']:
                    book = data['featured_book']
                    return {
                        'text': f"📖 {book.get('title', 'Book')}: {book.get('rating', 0)}/5⭐",
                        'priority': 8,
                        'category': 'books'
                    }
            
            # Generic highlight for any data with 'value' or 'count'
            if 'value' in data:
                return {
                    'text': f"{source.visualization_hints.get('icon', '📊')} {source.name}: {data['value']}",
                    'priority': source.priority,
                    'category': source.category
                }
            
        except Exception as e:
            logger.debug(f"Could not generate highlight for {source.name}: {e}")
        
        return None
    
    def _suggest_visualizations(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Suggest appropriate visualizations based on available data.
        
        Args:
            context: Aggregated data context
            
        Returns:
            List of visualization suggestions
        """
        suggestions = []
        
        # Check which visualizations are applicable
        for viz_name, viz in self.visualizations.items():
            # Check if we have data for this visualization type
            applicable_categories = []
            
            for category, sources in context['data_by_category'].items():
                if category in viz.data_types or any(dt in category for dt in viz.data_types):
                    applicable_categories.append(category)
            
            if applicable_categories:
                suggestions.append({
                    'visualization': viz_name,
                    'render_function': viz.render_function,
                    'categories': applicable_categories,
                    'priority': viz.priority
                })
        
        # Sort by priority
        suggestions.sort(key=lambda x: x['priority'], reverse=True)
        
        return suggestions
    
    def get_data_by_category(self, category: str) -> Dict[str, Any]:
        """Get all data for a specific category.
        
        Args:
            category: Category name (trading, mining, wallet, etc.)
            
        Returns:
            Dictionary of data sources in that category
        """
        result = {}
        
        for source_name, source in self.data_sources.items():
            if source.category == category and source.enabled:
                snapshot = self.data_snapshots.get(source_name, {})
                if snapshot.get('data'):
                    result[source_name] = snapshot['data']
        
        return result
    
    def get_active_categories(self) -> List[str]:
        """Get list of categories with active data.
        
        Returns:
            List of active category names
        """
        categories = set()
        cutoff = time.time() - 300  # 5 minutes
        
        for source_name, source in self.data_sources.items():
            snapshot = self.data_snapshots.get(source_name, {})
            last_update = snapshot.get('last_update')
            
            if last_update and last_update > cutoff and snapshot.get('data'):
                categories.add(source.category)
        
        return sorted(list(categories))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get aggregator statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            **self.stats,
            'registered_sources': len(self.data_sources),
            'enabled_sources': sum(1 for s in self.data_sources.values() if s.enabled),
            'active_categories': self.get_active_categories(),
            'data_coverage': {
                category: len(self.get_data_by_category(category))
                for category in self.get_active_categories()
            }
        }

# Global singleton instance
_universal_aggregator_instance = None

def get_universal_aggregator(event_bus=None) -> UniversalDataAggregator:
    """Get or create the global universal data aggregator instance."""
    global _universal_aggregator_instance
    if _universal_aggregator_instance is None:
        _universal_aggregator_instance = UniversalDataAggregator(event_bus)
    return _universal_aggregator_instance
