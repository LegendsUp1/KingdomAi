#!/usr/bin/env python3
"""
Kingdom AI - BookTok Context Aggregator
Aggregates live data from all system components for BookTok video generation.
Integrates with EventBus, Learning System, and Thoth/Ollama for AI storyboarding.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import aiohttp

logger = logging.getLogger("KingdomAI.BookTokAggregator")

class BookTokContextAggregator:
    """Aggregates live system data and creates AI-powered storyboards for BookTok videos."""
    
    def __init__(self, event_bus=None):
        """Initialize the BookTok Context Aggregator.
        
        Args:
            event_bus: System event bus for subscribing to data streams
        """
        self.event_bus = event_bus
        self.logger = logger
        
        # Use Universal Data Aggregator for ALL data sources
        try:
            from core.universal_data_aggregator import get_universal_aggregator
            self.universal_aggregator = get_universal_aggregator(event_bus)
            logger.info("✅ Universal Data Aggregator initialized - supports ALL data sources")
        except Exception as e:
            logger.error(f"Failed to initialize Universal Data Aggregator: {e}")
            self.universal_aggregator = None
        
        # Legacy data snapshots for backward compatibility
        # CRITICAL FIX: Initialize all keys to prevent KeyError
        self.data_snapshots = {
            'trading': {'prices': {}, 'portfolio': {}, 'risk': {}, 'ai_strategies': {}},
            'mining': {'status': {}, 'analytics': {}},
            'wallet': {'balances': {}},
            'blockchain': {'wallets': {}, 'transactions': [], 'performance': {}},
            'learning': {'metrics': {}, 'readiness': {}},
            'memory': {},
            'ai_brain': {'latest_response': {}, 'visual_request': {}},
            'vr': {},
            'code_gen': {'latest': {}},
            'books': {'user_library': [], 'trending': []}
        }
        
        # Initialize book data manager for book-specific features
        try:
            from core.book_data_manager import get_book_manager
            self.book_manager = get_book_manager(event_bus)
            logger.info("📚 Book Data Manager initialized in BookTok Aggregator")
        except Exception as e:
            logger.warning(f"Could not initialize Book Data Manager: {e}")
            self.book_manager = None
        
        # Initialize knowledge aggregator for dictionary, encyclopedia, learned data
        try:
            from core.knowledge_aggregator import get_knowledge_aggregator
            self.knowledge_aggregator = get_knowledge_aggregator(event_bus)
            logger.info("🔍 Knowledge Aggregator initialized - dictionary, encyclopedia, learned data")
        except Exception as e:
            logger.warning(f"Could not initialize Knowledge Aggregator: {e}")
            self.knowledge_aggregator = None
        
        # Storyboard cache
        self.latest_storyboard = None
        self.storyboard_timestamp = None
        
        # Connection to Thoth/Ollama
        self.thoth_connector = None
        try:
            from core.ollama_gateway import get_ollama_url
            self.ollama_endpoint = get_ollama_url() + "/api"
        except ImportError:
            self.ollama_endpoint = "http://127.0.0.1:11434/api"
        
        # Learning system reference
        self.learning_orchestrator = None
        
        # Web search capability
        self.web_search_enabled = False
        
        # Subscribe to events on initialization
        if self.event_bus:
            self._subscribe_to_events()
    
    def _subscribe_to_events(self):
        """Subscribe to all relevant system events for data aggregation."""
        try:
            # Trading events
            self.event_bus.subscribe_sync('trading.portfolio.snapshot', self._on_trading_snapshot)
            self.event_bus.subscribe_sync('trading.live_prices', self._on_trading_prices)
            self.event_bus.subscribe_sync('trading.risk.snapshot', self._on_risk_snapshot)
            self.event_bus.subscribe_sync('trading.ai.snapshot', self._on_ai_snapshot)
            
            # Mining events
            self.event_bus.subscribe_sync('mining.status', self._on_mining_status)
            self.event_bus.subscribe_sync('analytics.mining.coin_analytics', self._on_mining_analytics)
            
            # Wallet events  
            self.event_bus.subscribe_sync('wallet.balance.update', self._on_wallet_update)
            self.event_bus.subscribe_sync('blockchain.wallet_update', self._on_blockchain_wallet)
            
            # Blockchain events
            self.event_bus.subscribe_sync('blockchain.transaction_recorded', self._on_blockchain_tx)
            self.event_bus.subscribe_sync('blockchain.performance_update', self._on_blockchain_perf)
            
            # Learning/Memory events
            self.event_bus.subscribe_sync('learning.metrics', self._on_learning_metrics)
            self.event_bus.subscribe_sync('learning.readiness', self._on_learning_readiness)
            self.event_bus.subscribe_sync('memory.update', self._on_memory_update)
            
            # AI Brain events
            self.event_bus.subscribe_sync('ai.response', self._on_ai_response)
            self.event_bus.subscribe_sync('brain.visual.request', self._on_visual_request)
            
            # Book data events
            self.event_bus.subscribe_sync('book.data.ready', self._on_book_data)
            self.event_bus.subscribe_sync('book.library.update', self._on_library_update)
            self.event_bus.subscribe_sync('book.trending.update', self._on_trending_update)
            
            # VR events
            self.event_bus.subscribe_sync('vr.status', self._on_vr_status)
            
            # Code generation events
            self.event_bus.subscribe_sync('code.generated', self._on_code_generated)
            
            self.logger.info("✅ BookTok Aggregator subscribed to all system events")
        except Exception as e:
            self.logger.error(f"Failed to subscribe to events: {e}")
    
    # Event handlers to collect snapshots
    def _on_trading_snapshot(self, data: Dict[str, Any]):
        """Handle trading portfolio snapshots."""
        self.data_snapshots['trading']['portfolio'] = data
        self.data_snapshots['trading']['last_update'] = time.time()
    
    def _on_trading_prices(self, data: Dict[str, Any]):
        """Handle live price updates."""
        if 'prices' not in self.data_snapshots['trading']:
            self.data_snapshots['trading']['prices'] = {}
        self.data_snapshots['trading']['prices'].update(data)
    
    def _on_risk_snapshot(self, data: Dict[str, Any]):
        """Handle risk management snapshots."""
        self.data_snapshots['trading']['risk'] = data
    
    def _on_ai_snapshot(self, data: Dict[str, Any]):
        """Handle AI trading snapshots."""
        self.data_snapshots['trading']['ai_strategies'] = data
    
    def _on_mining_status(self, data: Dict[str, Any]):
        """Handle mining status updates."""
        self.data_snapshots['mining']['status'] = data
        self.data_snapshots['mining']['last_update'] = time.time()
    
    def _on_mining_analytics(self, data: Dict[str, Any]):
        """Handle mining analytics."""
        self.data_snapshots['mining']['analytics'] = data
    
    def _on_wallet_update(self, data: Dict[str, Any]):
        """Handle wallet balance updates."""
        if 'balances' not in self.data_snapshots['wallet']:
            self.data_snapshots['wallet']['balances'] = {}
        self.data_snapshots['wallet']['balances'].update(data)
        self.data_snapshots['wallet']['last_update'] = time.time()
    
    def _on_blockchain_wallet(self, data: Dict[str, Any]):
        """Handle blockchain wallet updates."""
        self.data_snapshots['blockchain']['wallets'] = data
    
    def _on_blockchain_tx(self, data: Dict[str, Any]):
        """Handle blockchain transactions."""
        if 'transactions' not in self.data_snapshots['blockchain']:
            self.data_snapshots['blockchain']['transactions'] = []
        self.data_snapshots['blockchain']['transactions'].append(data)
        # Keep only last 100 transactions
        self.data_snapshots['blockchain']['transactions'] = self.data_snapshots['blockchain']['transactions'][-100:]
    
    def _on_blockchain_perf(self, data: Dict[str, Any]):
        """Handle blockchain performance updates."""
        self.data_snapshots['blockchain']['performance'] = data
    
    def _on_learning_metrics(self, data: Dict[str, Any]):
        """Handle learning system metrics."""
        self.data_snapshots['learning']['metrics'] = data
        self.data_snapshots['learning']['last_update'] = time.time()
    
    def _on_learning_readiness(self, data: Dict[str, Any]):
        """Handle learning readiness status."""
        self.data_snapshots['learning']['readiness'] = data
    
    def _on_memory_update(self, data: Dict[str, Any]):
        """Handle memory system updates."""
        self.data_snapshots['memory'] = data
    
    def _on_ai_response(self, data: Dict[str, Any]):
        """Handle AI brain responses."""
        self.data_snapshots['ai_brain']['latest_response'] = data
    
    def _on_visual_request(self, data: Dict[str, Any]):
        """Handle visual generation requests."""
        self.data_snapshots['ai_brain']['visual_request'] = data
    
    def _on_vr_status(self, data: Dict[str, Any]):
        """Handle VR system status."""
        self.data_snapshots['vr'] = data
    
    def _on_code_generated(self, data: Dict[str, Any]):
        """Handle code generation events."""
        self.data_snapshots['code_gen']['latest'] = data
    
    def _on_book_data(self, data: Dict[str, Any]):
        """Handle book data ready event."""
        self.data_snapshots['books'] = data
        self.data_snapshots['books']['last_update'] = time.time()
    
    def _on_library_update(self, data: Dict[str, Any]):
        """Handle user library update."""
        if 'user_library' not in self.data_snapshots['books']:
            self.data_snapshots['books']['user_library'] = []
        self.data_snapshots['books']['user_library'] = data.get('library', [])
    
    def _on_trending_update(self, data: Dict[str, Any]):
        """Handle trending books update."""
        if 'trending' not in self.data_snapshots['books']:
            self.data_snapshots['books']['trending'] = []
        self.data_snapshots['books']['trending'] = data.get('books', [])
    
    async def aggregate_context(self, prompt: str = "", include_web_search: bool = False) -> Dict[str, Any]:
        """Aggregate all available context data from ALL sources.
        
        Args:
            prompt: User's BookTok prompt/theme
            include_web_search: Whether to include web search results
            
        Returns:
            Aggregated context dictionary with ALL system data
        """
        # Use Universal Aggregator to get ALL data
        if self.universal_aggregator:
            try:
                # Get comprehensive data from all sources
                context = await self.universal_aggregator.aggregate_all_data(
                    prompt=prompt,
                    filters={
                        'min_priority': 5,  # Include medium-high priority data
                        'max_age_seconds': 3600  # Last hour of data
                    }
                )
                
                # Add book-specific data if book manager available
                if self.book_manager:
                    try:
                        book_data = await self.book_manager.get_booktok_book_data(prompt)
                        context['book_data'] = book_data
                        
                        # Add book highlights
                        if book_data.get('featured_book'):
                            book = book_data['featured_book']
                            context['highlights'].append({
                                'text': f"📖 Featured: {book.get('title', 'Unknown')} by {', '.join(book.get('authors', ['Unknown']))}",
                                'priority': 9,
                                'category': 'books'
                            })
                            if book.get('rating'):
                                context['highlights'].append({
                                    'text': f"⭐ Rating: {book['rating']}/5 ({book.get('ratings_count', 0)} reviews)",
                                    'priority': 8,
                                    'category': 'books'
                                })
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch book data: {e}")
                
                # Add knowledge data (dictionary, encyclopedia, learned insights)
                if self.knowledge_aggregator:
                    try:
                        # Extract key terms from prompt for knowledge lookup
                        words = prompt.split()
                        key_terms = [w for w in words if len(w) > 4][:3]  # Get 3 longest words
                        
                        knowledge_data = {}
                        for term in key_terms:
                            term_knowledge = await self.knowledge_aggregator.aggregate_knowledge(term, include_all=False)
                            if term_knowledge.get('sources'):
                                knowledge_data[term] = term_knowledge
                        
                        context['knowledge_data'] = knowledge_data
                        
                        # Add knowledge highlights
                        for term, knowledge in knowledge_data.items():
                            for highlight in knowledge.get('highlights', [])[:2]:  # Top 2 per term
                                context['highlights'].append({
                                    'text': highlight,
                                    'priority': 7,
                                    'category': 'knowledge'
                                })
                        
                        # Add learned insights
                        learned_summary = self.knowledge_aggregator.get_learned_data_summary()
                        if learned_summary.get('total_insights', 0) > 0:
                            context['highlights'].append({
                                'text': f"🧠 {learned_summary['total_insights']} insights learned from system",
                                'priority': 7,
                                'category': 'knowledge'
                            })
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch knowledge data: {e}")
                
                # Add web search if requested
                if include_web_search:
                    web_results = await self._search_web(prompt)
                    if web_results:
                        context['web_search'] = web_results
                
                return context
                
            except Exception as e:
                self.logger.error(f"Universal aggregation failed: {e}")
        
        # Fallback to basic context if universal aggregator unavailable
        context = {
            'timestamp': datetime.now().isoformat(),
            'prompt': prompt,
            'system_data': {},
            'statistics': {},
            'highlights': [],
            'book_data': {},
            'data_by_category': {},
            'data_by_source': {}
        }
        
        # Aggregate trading data
        if self.data_snapshots['trading']:
            portfolio = self.data_snapshots['trading'].get('portfolio', {})
            context['system_data']['trading'] = {
                'total_value': portfolio.get('total_value', 0),
                'daily_pnl': portfolio.get('daily_pnl', 0),
                'positions': portfolio.get('position_count', 0),
                'top_gainers': portfolio.get('top_gainers', [])[:3],
                'active_strategies': self.data_snapshots['trading'].get('ai_strategies', {}).get('active', [])
            }
            
            # Add highlight if significant profit
            if portfolio.get('daily_pnl', 0) > 1000:
                context['highlights'].append(f"📈 Daily Profit: ${portfolio['daily_pnl']:,.2f}")
        
        # Aggregate mining data
        if self.data_snapshots['mining']:
            mining_status = self.data_snapshots['mining'].get('status', {})
            context['system_data']['mining'] = {
                'active_miners': mining_status.get('active_count', 0),
                'total_hashrate': mining_status.get('total_hashrate', '0 H/s'),
                'coins_mined': mining_status.get('coins', []),
                'daily_revenue': mining_status.get('daily_revenue', 0)
            }
            
            # Add highlight if mining revenue
            if mining_status.get('daily_revenue', 0) > 100:
                context['highlights'].append(f"⛏️ Mining Revenue: ${mining_status['daily_revenue']:,.2f}/day")
        
        # Aggregate wallet data
        if self.data_snapshots['wallet']:
            wallets = self.data_snapshots['wallet'].get('balances', {})
            total_balance = sum(w.get('usd_value', 0) for w in wallets.values())
            context['system_data']['wallet'] = {
                'total_balance_usd': total_balance,
                'active_wallets': len(wallets),
                'top_holdings': sorted(wallets.items(), key=lambda x: x[1].get('usd_value', 0), reverse=True)[:3]
            }
            
            # Add highlight for large balances
            if total_balance > 10000:
                context['highlights'].append(f"💰 Total Balance: ${total_balance:,.2f}")
        
        # Aggregate blockchain data
        if self.data_snapshots['blockchain']:
            recent_txs = self.data_snapshots['blockchain'].get('transactions', [])
            context['system_data']['blockchain'] = {
                'recent_transactions': len(recent_txs),
                'networks_active': self.data_snapshots['blockchain'].get('performance', {}).get('networks', 0),
                'gas_fees': self.data_snapshots['blockchain'].get('performance', {}).get('avg_gas', 'N/A')
            }
        
        # Aggregate learning system data
        if self.data_snapshots['learning']:
            learning = self.data_snapshots['learning']
            context['system_data']['learning'] = {
                'readiness': learning.get('readiness', {}).get('state', 'UNKNOWN'),
                'events_processed': learning.get('metrics', {}).get('total_events', 0),
                'active_sources': learning.get('metrics', {}).get('active_sources', 0),
                'predator_mode': learning.get('readiness', {}).get('predator_mode_active', False)
            }
            
            # Add highlight for predator mode
            if learning.get('readiness', {}).get('predator_mode_active', False):
                context['highlights'].append("🦁 PREDATOR MODE ACTIVE")
        
        # Calculate statistics
        context['statistics'] = {
            'data_sources_active': sum(1 for d in self.data_snapshots.values() if d),
            'total_highlights': len(context['highlights']),
            'last_update': max(
                (d.get('last_update', 0) for d in self.data_snapshots.values() if isinstance(d, dict)), 
                default=0
            )
        }
        
        # Web search integration (if requested)
        if include_web_search and prompt:
            web_results = await self._search_web(prompt)
            if web_results:
                context['web_search'] = web_results
                context['highlights'].append(f"🔍 {len(web_results.get('results', []))} web sources found")
        
        return context
    
    async def generate_storyboard(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a BookTok storyboard using AI brain (Thoth/Ollama).
        
        Args:
            prompt: User's BookTok prompt
            context: Aggregated context data
            
        Returns:
            Storyboard with scenes, overlays, and metadata
        """
        storyboard = {
            'title': prompt[:100],
            'duration_seconds': 30,
            'aspect_ratio': '9:16',
            'scenes': [],
            'text_overlays': [],
            'hashtags': [],
            'call_to_action': '',
            'music_suggestion': 'emotional, cinematic',
            'generated_at': datetime.now().isoformat()
        }
        
        # Prepare AI prompt with context
        ai_prompt = f"""
Create a BookTok-style video storyboard based on this Kingdom AI system data.

USER REQUEST: {prompt}

SYSTEM HIGHLIGHTS:
{json.dumps(context.get('highlights', []), indent=2)}

CURRENT DATA:
- Trading: {json.dumps(context.get('system_data', {}).get('trading', {}), indent=2)}
- Mining: {json.dumps(context.get('system_data', {}).get('mining', {}), indent=2)}
- Wallet: {json.dumps(context.get('system_data', {}).get('wallet', {}), indent=2)}
- Learning: {json.dumps(context.get('system_data', {}).get('learning', {}), indent=2)}

Create a compelling 30-second vertical video storyboard with:
1. Hook (0-3 seconds) - attention-grabbing opening
2. Build-up (3-10 seconds) - show the data/story
3. Climax (10-20 seconds) - main value/insight
4. Call to action (20-30 seconds) - what to do next

Format your response as JSON with:
- scenes: array of {start_time, end_time, description, text_overlay}
- hashtags: array of relevant hashtags
- call_to_action: final CTA text
"""
        
        # Try to get AI-generated storyboard
        try:
            if self.event_bus:
                # Request via event bus
                request_id = f"booktok_{int(time.time()*1000)}"
                self.event_bus.publish('ai.query', {
                    'prompt': ai_prompt,
                    'request_id': request_id,
                    'sender': 'BookTokAggregator',
                    'format': 'json'
                })
                
                # Wait for response (with timeout)
                await asyncio.sleep(2)  # Simple wait for demo
                
                # Check if we got a response
                ai_response = self.data_snapshots.get('ai_brain', {}).get('latest_response', {})
                if ai_response and ai_response.get('request_id') == request_id:
                    try:
                        response_data = json.loads(ai_response.get('response', '{}'))
                        storyboard.update(response_data)
                    except:
                        pass
            
            # Direct Ollama call as fallback
            if not storyboard['scenes']:
                storyboard = await self._call_ollama_direct(ai_prompt, storyboard)
        except Exception as e:
            self.logger.error(f"Failed to generate AI storyboard: {e}")
        
        # Fallback storyboard if AI fails
        if not storyboard['scenes']:
            storyboard = self._generate_fallback_storyboard(prompt, context)
        
        # Cache the storyboard
        self.latest_storyboard = storyboard
        self.storyboard_timestamp = time.time()
        
        # Publish storyboard event
        if self.event_bus:
            self.event_bus.publish('booktok.storyboard.ready', storyboard)
        
        return storyboard
    
    async def _call_ollama_direct(self, prompt: str, storyboard: Dict[str, Any]) -> Dict[str, Any]:
        """Direct call to Ollama API via orchestrator."""
        try:
            try:
                from core.ollama_gateway import orchestrator
                _book_model = orchestrator.get_model_for_task("creative_studio")
            except ImportError:
                _book_model = "cogito:latest"
            async with aiohttp.ClientSession() as session:
                payload = {
                    'model': _book_model,
                    'prompt': prompt,
                    'format': 'json',
                    'stream': False,
                    'keep_alive': -1,
                    'options': {'num_gpu': 999},
                }
                async with session.post(f"{self.ollama_endpoint}/generate", json=payload, timeout=aiohttp.ClientTimeout(total=None, sock_read=120)) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        response_data = json.loads(result.get('response', '{}'))
                        storyboard.update(response_data)
        except Exception as e:
            self.logger.debug(f"Ollama direct call failed: {e}")
        return storyboard
    
    def _generate_fallback_storyboard(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a fallback storyboard when AI is unavailable."""
        highlights = context.get('highlights', [])
        
        scenes = [
            {
                'start_time': 0,
                'end_time': 3,
                'description': 'Kingdom AI logo animation with glitch effect',
                'text_overlay': 'KINGDOM AI PRESENTS'
            },
            {
                'start_time': 3,
                'end_time': 8,
                'description': 'Data visualization of system metrics',
                'text_overlay': highlights[0] if highlights else 'Real-Time Analytics'
            },
            {
                'start_time': 8,
                'end_time': 15,
                'description': 'Trading charts and profit graphs animating',
                'text_overlay': highlights[1] if len(highlights) > 1 else f'Trading: ${context.get("system_data", {}).get("trading", {}).get("daily_pnl", 0):,.2f}'
            },
            {
                'start_time': 15,
                'end_time': 22,
                'description': 'Mining rigs and blockchain visualization',
                'text_overlay': highlights[2] if len(highlights) > 2 else 'Multi-Chain Operations'
            },
            {
                'start_time': 22,
                'end_time': 27,
                'description': 'AI brain neural network animation',
                'text_overlay': 'Powered by AI'
            },
            {
                'start_time': 27,
                'end_time': 30,
                'description': 'Call to action with website/link',
                'text_overlay': 'Join Kingdom AI Today'
            }
        ]
        
        return {
            'title': prompt[:100],
            'duration_seconds': 30,
            'aspect_ratio': '9:16',
            'scenes': scenes,
            'text_overlays': [s['text_overlay'] for s in scenes],
            'hashtags': ['#KingdomAI', '#AITrading', '#CryptoMining', '#BookTok', '#TechTok', '#FinTech'],
            'call_to_action': 'Learn more at kingdom.ai',
            'music_suggestion': 'electronic, upbeat, tech',
            'generated_at': datetime.now().isoformat()
        }
    
    async def _search_web(self, query: str) -> Dict[str, Any]:
        """Search web for relevant content via DuckDuckGo Instant Answer API."""
        import urllib.request, urllib.parse, json as _json
        try:
            safe_q = urllib.parse.quote_plus(query)
            url = f"https://api.duckduckgo.com/?q={safe_q}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(url, headers={"User-Agent": "KingdomAI/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = _json.loads(resp.read())
            results = []
            if data.get("AbstractText"):
                results.append({"title": data.get("Heading", query), "snippet": data["AbstractText"], "url": data.get("AbstractURL", "")})
            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({"title": topic.get("Text", "")[:80], "snippet": topic.get("Text", ""), "url": topic.get("FirstURL", "")})
            return {"query": query, "results": results, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            self.logger.warning(f"Web search failed for '{query}': {e}")
            return {"query": query, "results": [], "timestamp": datetime.now().isoformat()}
    
    async def create_booktok_context(self, prompt: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Main entry point: aggregate context and generate storyboard.
        
        Args:
            prompt: User's BookTok prompt
            
        Returns:
            Tuple of (context, storyboard)
        """
        # Aggregate all system data
        context = await self.aggregate_context(prompt, include_web_search=True)
        
        # Generate AI storyboard
        storyboard = await self.generate_storyboard(prompt, context)
        
        # Publish complete context event
        if self.event_bus:
            self.event_bus.publish('booktok.context.ready', {
                'prompt': prompt,
                'context': context,
                'storyboard': storyboard,
                'timestamp': datetime.now().isoformat()
            })
        
        return context, storyboard

# Global singleton instance
_aggregator_instance = None

def get_booktok_aggregator(event_bus=None) -> BookTokContextAggregator:
    """Get or create the global BookTok aggregator instance."""
    global _aggregator_instance
    if _aggregator_instance is None:
        _aggregator_instance = BookTokContextAggregator(event_bus)
    return _aggregator_instance
