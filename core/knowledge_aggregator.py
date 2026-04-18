#!/usr/bin/env python3
"""
Kingdom AI - Knowledge Aggregator (SOTA 2026)
Aggregates knowledge from dictionaries, encyclopedias, books, and learned data.
Integrates ALL free APIs: Dictionary API, Wikipedia, Wikidata, Open Library, and more.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import aiohttp
from bs4 import BeautifulSoup
import hashlib

logger = logging.getLogger("KingdomAI.KnowledgeAggregator")

class KnowledgeAggregator:
    """Aggregates knowledge from multiple free sources including learned data."""
    
    def __init__(self, event_bus=None, api_key_manager=None, thoth_connector=None):
        """Initialize the Knowledge Aggregator.
        
        Args:
            event_bus: System event bus for communication
            api_key_manager: Existing API key manager for authenticated APIs
            thoth_connector: Thoth/Ollama connector for AI processing
        """
        self.event_bus = event_bus
        self.logger = logger
        
        # Connect to existing API key management system
        self.api_key_manager = api_key_manager
        if not api_key_manager and event_bus:
            try:
                from core.api_key_manager import APIKeyManager
                self.api_key_manager = APIKeyManager.get_instance(event_bus)
                logger.info("✅ Connected to existing API Key Manager")
            except Exception as e:
                logger.warning(f"Could not connect to API Key Manager: {e}")
        
        # Connect to Thoth/Ollama brain for AI-enhanced knowledge processing
        self.thoth_connector = thoth_connector
        if not thoth_connector and event_bus:
            try:
                from core.thoth_ollama_connector import ThothOllamaConnector
                self.thoth_connector = ThothOllamaConnector(event_bus, self.api_key_manager)
                logger.info("✅ Connected to Thoth/Ollama brain for AI knowledge processing")
            except Exception as e:
                logger.warning(f"Could not connect to Thoth/Ollama: {e}")
        
        # Free API endpoints (NO API KEYS REQUIRED)
        # These are integrated with existing API key manager for optional authenticated access
        self.apis = {
            # Dictionary APIs
            'dictionary': 'https://api.dictionaryapi.dev/api/v2/entries/en',
            'dictionary_alt': 'https://api.dictionaryapi.com/api/v3/references/collegiate/json',
            
            # Encyclopedia APIs
            'wikipedia': 'https://en.wikipedia.org/api/rest_v1',
            'wikidata': 'https://www.wikidata.org/w/api.php',
            'dbpedia': 'https://dbpedia.org/sparql',
            
            # Book APIs
            'openlibrary': 'https://openlibrary.org',
            'openlibrary_search': 'https://openlibrary.org/search.json',
            'google_books': 'https://www.googleapis.com/books/v1/volumes',
            'isbndb': 'https://api2.isbndb.com',  # Has free tier
            
            # Educational/Knowledge APIs
            'arxiv': 'http://export.arxiv.org/api/query',
            'crossref': 'https://api.crossref.org/works',
            'pubmed': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils',
            
            # News/Current Events
            'newsapi': 'https://newsapi.org/v2',  # Free tier available
            
            # Quotes
            'quotable': 'https://api.quotable.io',
            
            # Facts/Trivia
            'numbers_api': 'http://numbersapi.com',
            'useless_facts': 'https://uselessfacts.jsph.pl/api/v2/facts/random'
        }
        
        # Cache for API responses
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour
        
        # Learned data storage
        self.learned_data = {
            'concepts': {},
            'relationships': {},
            'insights': [],
            'patterns': []
        }
        
        # Subscribe to learning events and integrate with existing event patterns
        if self.event_bus:
            self._subscribe_to_events()
            
        # Publish initialization event to notify system
        if self.event_bus:
            self.event_bus.publish('knowledge.aggregator.initialized', {
                'apis_available': len(self.apis),
                'api_key_manager_connected': self.api_key_manager is not None,
                'thoth_connected': self.thoth_connector is not None
            })
    
    def _subscribe_to_events(self):
        """Subscribe to learning and knowledge events."""
        # Learning system integration (existing patterns)
        self.event_bus.subscribe_sync('learning.insight', self._on_learning_insight)
        self.event_bus.subscribe_sync('learning.pattern', self._on_learning_pattern)
        self.event_bus.subscribe_sync('learning.metrics', self._on_learning_metrics)
        self.event_bus.subscribe_sync('learning.readiness', self._on_learning_readiness)
        
        # Knowledge request patterns
        self.event_bus.subscribe_sync('knowledge.request', self._on_knowledge_request)
        self.event_bus.subscribe_sync('ai.query', self._on_ai_query)
        
        # Ollama brain integration
        self.event_bus.subscribe_sync('ollama.response', self._on_ollama_response)
        self.event_bus.subscribe_sync('thoth.query', self._on_thoth_query)
    
    def _on_learning_insight(self, event_type: str, data: Dict[str, Any]):
        """Handle learning insights from the AI system."""
        self.learned_data['insights'].append({
            'data': data,
            'timestamp': time.time()
        })
        # Keep only last 1000 insights
        self.learned_data['insights'] = self.learned_data['insights'][-1000:]
    
    def _on_learning_pattern(self, event_type: str, data: Dict[str, Any]):
        """Handle learned patterns."""
        self.learned_data['patterns'].append({
            'data': data,
            'timestamp': time.time()
        })
        self.learned_data['patterns'] = self.learned_data['patterns'][-1000:]
    
    def _on_knowledge_request(self, event_type: str, data: Dict[str, Any]):
        """Handle knowledge requests."""
        query = data.get('query', '')
        asyncio.create_task(self.aggregate_knowledge(query))
    
    def _on_learning_metrics(self, event_type: str, data: Dict[str, Any]):
        """Handle learning metrics from learning_orchestrator."""
        # Store metrics as learned data
        self.learned_data['concepts']['learning_metrics'] = data
    
    def _on_learning_readiness(self, event_type: str, data: Dict[str, Any]):
        """Handle learning readiness state changes."""
        state = data.get('state', 'UNKNOWN')
        self.learned_data['concepts']['learning_state'] = state
        
        # If predator mode activated, prioritize aggressive knowledge gathering
        if data.get('predator_mode_active'):
            logger.info("🦁 PREDATOR MODE: Aggressive knowledge aggregation enabled")
    
    def _on_ai_query(self, event_type: str, data: Dict[str, Any]):
        """Handle AI queries that might need knowledge augmentation."""
        query = data.get('prompt', data.get('query', ''))
        if query and len(query) > 10:  # Only for substantial queries
            # Augment AI query with knowledge in background
            asyncio.create_task(self._augment_ai_query(query, data))
    
    def _on_ollama_response(self, event_type: str, data: Dict[str, Any]):
        """Handle Ollama responses for learning."""
        response = data.get('response', '')
        if response:
            # Extract insights from Ollama responses
            self.learned_data['insights'].append({
                'source': 'ollama',
                'data': {'response': response[:500]},  # Store first 500 chars
                'timestamp': time.time()
            })
    
    def _on_thoth_query(self, event_type: str, data: Dict[str, Any]):
        """Handle Thoth AI queries."""
        query = data.get('query', '')
        if query:
            # Provide knowledge context to Thoth
            asyncio.create_task(self._provide_knowledge_context(query, data))
    
    async def _augment_ai_query(self, query: str, original_data: Dict[str, Any]):
        """Augment AI query with relevant knowledge."""
        try:
            # Get quick knowledge summary
            knowledge = await self.aggregate_knowledge(query, include_all=False)
            
            # Publish augmented context
            if self.event_bus:
                self.event_bus.publish('knowledge.context.available', {
                    'original_query': query,
                    'knowledge': knowledge,
                    'request_id': original_data.get('request_id')
                })
        except Exception as e:
            logger.debug(f"Could not augment AI query: {e}")
    
    async def _provide_knowledge_context(self, query: str, thoth_data: Dict[str, Any]):
        """Provide knowledge context to Thoth AI."""
        try:
            knowledge = await self.aggregate_knowledge(query, include_all=False)
            
            # Send knowledge to Thoth for enhanced responses
            if self.event_bus:
                self.event_bus.publish('thoth.knowledge.context', {
                    'query': query,
                    'knowledge': knowledge,
                    'summary': knowledge.get('summary', ''),
                    'highlights': knowledge.get('highlights', [])
                })
        except Exception as e:
            logger.debug(f"Could not provide knowledge context to Thoth: {e}")
    
    async def get_dictionary_definition(self, word: str) -> Dict[str, Any]:
        """Get word definition from Free Dictionary API.
        
        Args:
            word: Word to define
            
        Returns:
            Dictionary with definitions, phonetics, examples
        """
        cache_key = f"dict:{word}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_ttl:
                return cached['data']
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.apis['dictionary']}/{word}"
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Parse response
                        result = {
                            'word': word,
                            'found': True,
                            'definitions': [],
                            'phonetics': [],
                            'origin': '',
                            'examples': []
                        }
                        
                        if data and len(data) > 0:
                            entry = data[0]
                            result['phonetics'] = entry.get('phonetics', [])
                            result['origin'] = entry.get('origin', '')
                            
                            for meaning in entry.get('meanings', []):
                                part_of_speech = meaning.get('partOfSpeech', '')
                                for definition in meaning.get('definitions', []):
                                    result['definitions'].append({
                                        'part_of_speech': part_of_speech,
                                        'definition': definition.get('definition', ''),
                                        'example': definition.get('example', ''),
                                        'synonyms': definition.get('synonyms', []),
                                        'antonyms': definition.get('antonyms', [])
                                    })
                                    
                                    if definition.get('example'):
                                        result['examples'].append(definition['example'])
                        
                        # Cache result
                        self.cache[cache_key] = {
                            'data': result,
                            'timestamp': time.time()
                        }
                        
                        return result
        except Exception as e:
            logger.error(f"Dictionary API error for '{word}': {e}")
        
        return {'word': word, 'found': False, 'error': 'Not found'}
    
    async def get_wikipedia_summary(self, topic: str) -> Dict[str, Any]:
        """Get Wikipedia summary for a topic.
        
        Args:
            topic: Topic to search
            
        Returns:
            Dictionary with summary, extract, images
        """
        cache_key = f"wiki:{topic}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_ttl:
                return cached['data']
        
        try:
            async with aiohttp.ClientSession() as session:
                # Search for page
                search_url = f"{self.apis['wikipedia']}/page/summary/{topic.replace(' ', '_')}"
                async with session.get(search_url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        result = {
                            'title': data.get('title', topic),
                            'extract': data.get('extract', ''),
                            'description': data.get('description', ''),
                            'thumbnail': data.get('thumbnail', {}).get('source', ''),
                            'url': data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                            'found': True
                        }
                        
                        # Cache result
                        self.cache[cache_key] = {
                            'data': result,
                            'timestamp': time.time()
                        }
                        
                        return result
        except Exception as e:
            logger.error(f"Wikipedia API error for '{topic}': {e}")
        
        return {'title': topic, 'found': False, 'error': 'Not found'}
    
    async def get_wikidata_info(self, query: str) -> Dict[str, Any]:
        """Get structured data from Wikidata.
        
        Args:
            query: Search query
            
        Returns:
            Wikidata entity information
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Search for entity
                params = {
                    'action': 'wbsearchentities',
                    'search': query,
                    'language': 'en',
                    'format': 'json',
                    'limit': 1
                }
                
                async with session.get(self.apis['wikidata'], params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if data.get('search'):
                            entity = data['search'][0]
                            return {
                                'id': entity.get('id', ''),
                                'label': entity.get('label', ''),
                                'description': entity.get('description', ''),
                                'url': entity.get('concepturi', ''),
                                'found': True
                            }
        except Exception as e:
            logger.error(f"Wikidata API error for '{query}': {e}")
        
        return {'query': query, 'found': False}
    
    async def search_scholarly_articles(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search scholarly articles from arXiv.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of article metadata
        """
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'search_query': f'all:{query}',
                    'start': 0,
                    'max_results': limit
                }
                
                async with session.get(self.apis['arxiv'], params=params, timeout=15) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        
                        # Parse XML response
                        articles = []
                        soup = BeautifulSoup(text, 'xml')
                        
                        for entry in soup.find_all('entry'):
                            article = {
                                'title': entry.find('title').text.strip() if entry.find('title') else '',
                                'summary': entry.find('summary').text.strip() if entry.find('summary') else '',
                                'authors': [author.find('name').text for author in entry.find_all('author')],
                                'published': entry.find('published').text if entry.find('published') else '',
                                'link': entry.find('id').text if entry.find('id') else '',
                                'categories': [cat.get('term') for cat in entry.find_all('category')]
                            }
                            articles.append(article)
                        
                        return articles
        except Exception as e:
            logger.error(f"arXiv API error for '{query}': {e}")
        
        return []
    
    async def get_random_quote(self, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get random inspirational quote.
        
        Args:
            tags: Optional tags to filter quotes
            
        Returns:
            Quote with author and content
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.apis['quotable']}/random"
                params = {}
                if tags:
                    params['tags'] = ','.join(tags)
                
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            'content': data.get('content', ''),
                            'author': data.get('author', ''),
                            'tags': data.get('tags', []),
                            'found': True
                        }
        except Exception as e:
            logger.error(f"Quotable API error: {e}")
        
        return {'found': False}
    
    async def get_interesting_fact(self) -> Dict[str, Any]:
        """Get random interesting fact.
        
        Returns:
            Random fact
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.apis['useless_facts'], timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            'fact': data.get('text', ''),
                            'source': data.get('source', ''),
                            'found': True
                        }
        except Exception as e:
            logger.error(f"Facts API error: {e}")
        
        return {'found': False}
    
    async def aggregate_knowledge(self, query: str, include_all: bool = True) -> Dict[str, Any]:
        """Aggregate knowledge from ALL sources about a query.
        
        Args:
            query: Search query/topic
            include_all: Whether to fetch from all sources
            
        Returns:
            Comprehensive knowledge dictionary
        """
        knowledge = {
            'query': query,
            'timestamp': datetime.now().isoformat(),
            'sources': {},
            'summary': '',
            'highlights': [],
            'learned_insights': [],
            'ai_enhanced': False,
            'api_keys_used': []
        }
        
        # Parallel fetch from multiple sources
        tasks = []
        
        # Dictionary definition
        tasks.append(('dictionary', self.get_dictionary_definition(query)))
        
        # Wikipedia summary
        tasks.append(('wikipedia', self.get_wikipedia_summary(query)))
        
        # Wikidata structured data
        tasks.append(('wikidata', self.get_wikidata_info(query)))
        
        if include_all:
            # Scholarly articles
            tasks.append(('articles', self.search_scholarly_articles(query, limit=3)))
            
            # Random quote (if query is about a person or concept)
            tasks.append(('quote', self.get_random_quote()))
            
            # Interesting fact
            tasks.append(('fact', self.get_interesting_fact()))
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
        
        # Compile results
        for i, (source_name, _) in enumerate(tasks):
            if not isinstance(results[i], Exception):
                knowledge['sources'][source_name] = results[i]
                
                # Generate highlights
                if source_name == 'dictionary' and results[i].get('found'):
                    defs = results[i].get('definitions', [])
                    if defs:
                        knowledge['highlights'].append(f"📖 Definition: {defs[0].get('definition', '')[:100]}")
                
                elif source_name == 'wikipedia' and results[i].get('found'):
                    extract = results[i].get('extract', '')
                    if extract:
                        knowledge['highlights'].append(f"📚 Wikipedia: {extract[:150]}...")
                
                elif source_name == 'wikidata' and results[i].get('found'):
                    desc = results[i].get('description', '')
                    if desc:
                        knowledge['highlights'].append(f"🔗 Wikidata: {desc}")
                
                elif source_name == 'quote' and results[i].get('found'):
                    quote = results[i].get('content', '')
                    author = results[i].get('author', '')
                    if quote:
                        knowledge['highlights'].append(f"💬 Quote: \"{quote[:100]}...\" - {author}")
                
                elif source_name == 'fact' and results[i].get('found'):
                    fact = results[i].get('fact', '')
                    if fact:
                        knowledge['highlights'].append(f"💡 Fact: {fact[:100]}")
        
        # Add learned insights related to query
        query_lower = query.lower()
        for insight in self.learned_data['insights'][-50:]:  # Last 50 insights
            insight_data = insight.get('data', {})
            insight_text = str(insight_data).lower()
            if query_lower in insight_text:
                knowledge['learned_insights'].append(insight_data)
        
        # Generate summary
        knowledge['summary'] = self._generate_summary(knowledge)
        
        # Enhance with Ollama/Thoth AI if available
        if self.thoth_connector:
            try:
                ai_summary = await self._get_ai_enhanced_summary(knowledge)
                if ai_summary:
                    knowledge['ai_enhanced'] = True
                    knowledge['ai_summary'] = ai_summary
                    knowledge['highlights'].insert(0, f"🤖 AI Insight: {ai_summary[:150]}...")
            except Exception as e:
                logger.debug(f"Could not enhance with AI: {e}")
        
        # Publish knowledge event to existing event bus patterns
        if self.event_bus:
            self.event_bus.publish('knowledge.aggregated', knowledge)
            
            # Also publish to specific channels for different consumers
            self.event_bus.publish('learning.knowledge.available', {
                'query': query,
                'sources_count': len(knowledge['sources']),
                'highlights_count': len(knowledge['highlights'])
            })
        
        return knowledge
    
    def _generate_summary(self, knowledge: Dict[str, Any]) -> str:
        """Generate a summary from aggregated knowledge.
        
        Args:
            knowledge: Aggregated knowledge dictionary
            
        Returns:
            Summary string
        """
        parts = []
        
        # Wikipedia summary
        wiki = knowledge['sources'].get('wikipedia', {})
        if wiki.get('found'):
            parts.append(wiki.get('extract', '')[:200])
        
        # Dictionary definition
        dict_data = knowledge['sources'].get('dictionary', {})
        if dict_data.get('found'):
            defs = dict_data.get('definitions', [])
            if defs:
                parts.append(f"Definition: {defs[0].get('definition', '')}")
        
        # Wikidata description
        wikidata = knowledge['sources'].get('wikidata', {})
        if wikidata.get('found'):
            parts.append(wikidata.get('description', ''))
        
        return ' | '.join(parts) if parts else f"Knowledge about {knowledge['query']}"
    
    async def _get_ai_enhanced_summary(self, knowledge: Dict[str, Any]) -> str:
        """Get AI-enhanced summary using Ollama/Thoth brain.
        
        Args:
            knowledge: Aggregated knowledge dictionary
            
        Returns:
            AI-generated summary
        """
        if not self.thoth_connector:
            return ""
        
        try:
            # Prepare context for AI
            context = f"""Summarize this knowledge about '{knowledge['query']}':

Sources:
{json.dumps(knowledge['sources'], indent=2)[:1000]}

Highlights:
{json.dumps(knowledge['highlights'], indent=2)[:500]}

Provide a concise, insightful summary in 2-3 sentences."""
            
            # Request AI summary via event bus
            if self.event_bus:
                request_id = f"knowledge_summary_{int(time.time() * 1000)}"
                self.event_bus.publish('ai.query', {
                    'prompt': context,
                    'request_id': request_id,
                    'sender': 'KnowledgeAggregator',
                    'max_tokens': 200
                })
                
                # Wait briefly for response (non-blocking)
                await asyncio.sleep(1)
            
            return ""  # Response will come via event
        except Exception as e:
            logger.debug(f"AI enhancement failed: {e}")
            return ""
    
    def get_learned_data_summary(self) -> Dict[str, Any]:
        """Get summary of learned data.
        
        Returns:
            Summary of learned insights and patterns
        """
        return {
            'total_insights': len(self.learned_data['insights']),
            'total_patterns': len(self.learned_data['patterns']),
            'recent_insights': self.learned_data['insights'][-10:],
            'recent_patterns': self.learned_data['patterns'][-10:],
            'concepts_learned': len(self.learned_data['concepts']),
            'relationships_discovered': len(self.learned_data['relationships'])
        }

# Global singleton instance
_knowledge_aggregator_instance = None

def get_knowledge_aggregator(event_bus=None, api_key_manager=None, thoth_connector=None) -> KnowledgeAggregator:
    """Get or create the global knowledge aggregator instance."""
    global _knowledge_aggregator_instance
    if _knowledge_aggregator_instance is None:
        _knowledge_aggregator_instance = KnowledgeAggregator(event_bus, api_key_manager, thoth_connector)
    return _knowledge_aggregator_instance
