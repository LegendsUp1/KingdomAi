"""
Web Scraper Integration - Web scraping capabilities for AI.

This module enables Kingdom AI to fetch web pages, search the web, and extract
information from URLs provided by users.
"""

import logging
import asyncio
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class WebScraperIntegration:
    """Web scraping capabilities for AI."""
    
    def __init__(self):
        """Initialize the Web Scraper Integration."""
        self.session = None
        self.logger = logger
        self.cache = {}
        self.cache_timeout = 300  # 5 minutes
        
    async def initialize(self):
        """Initialize HTTP session."""
        try:
            import aiohttp
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
            self.logger.info("✅ Web scraper initialized")
        except ImportError:
            self.logger.warning("⚠️ aiohttp not available, web scraping disabled")
    
    async def fetch_url(self, url: str) -> dict:
        """Fetch and parse web page.
        
        Args:
            url: URL to fetch
            
        Returns:
            Dict with success status, content, and metadata
        """
        try:
            # Check cache
            if url in self.cache:
                cache_entry = self.cache[url]
                age = (datetime.now() - cache_entry['timestamp']).total_seconds()
                if age < self.cache_timeout:
                    self.logger.info(f"✅ Returning cached content for {url}")
                    return cache_entry['data']
            
            if not self.session:
                await self.initialize()
            
            if not self.session:
                return {
                    'success': False,
                    'error': 'Web scraping not available (aiohttp not installed)',
                    'url': url
                }
            
            self.logger.info(f"🌐 Fetching URL: {url}")
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Parse HTML
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Remove script and style elements
                        for script in soup(["script", "style"]):
                            script.decompose()
                        
                        # Extract text content
                        text = soup.get_text(separator='\n', strip=True)
                        
                        # Extract title
                        title = soup.title.string if soup.title else 'No title'
                        
                        # Extract meta description
                        description = ''
                        meta_desc = soup.find('meta', attrs={'name': 'description'})
                        if meta_desc and meta_desc.get('content'):
                            description = meta_desc['content']
                        
                        result = {
                            'success': True,
                            'url': url,
                            'title': title,
                            'description': description,
                            'content': text[:5000],  # Limit to 5000 chars
                            'full_length': len(text),
                            'status': response.status,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        # Cache result
                        self.cache[url] = {
                            'data': result,
                            'timestamp': datetime.now()
                        }
                        
                        self.logger.info(f"✅ Fetched {len(text)} chars from {url}")
                        return result
                        
                    except ImportError:
                        # Fallback without BeautifulSoup
                        self.logger.warning("BeautifulSoup not available, returning raw HTML")
                        return {
                            'success': True,
                            'url': url,
                            'title': 'Unknown',
                            'content': html[:5000],
                            'status': response.status,
                            'note': 'Raw HTML (BeautifulSoup not available)'
                        }
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}',
                        'url': url,
                        'status': response.status
                    }
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': 'Request timeout',
                'url': url
            }
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return {
                'success': False,
                'error': str(e),
                'url': url
            }
    
    async def search_web(self, query: str) -> dict:
        """Search the web for information.
        
        Args:
            query: Search query
            
        Returns:
            Dict with search results
        """
        try:
            if not self.session:
                await self.initialize()
            
            if not self.session:
                return {
                    'success': False,
                    'error': 'Web scraping not available'
                }
            
            # Use DuckDuckGo API (no API key required)
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json"
            
            self.logger.info(f"🔍 Searching web for: {query}")
            
            async with self.session.get(search_url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    results = []
                    
                    # Extract related topics
                    for topic in data.get('RelatedTopics', [])[:5]:
                        if isinstance(topic, dict) and 'Text' in topic:
                            results.append({
                                'text': topic.get('Text', ''),
                                'url': topic.get('FirstURL', ''),
                                'source': 'DuckDuckGo'
                            })
                    
                    # Extract abstract if available
                    abstract = data.get('Abstract', '')
                    abstract_url = data.get('AbstractURL', '')
                    
                    return {
                        'success': True,
                        'query': query,
                        'abstract': abstract,
                        'abstract_url': abstract_url,
                        'results': results,
                        'result_count': len(results)
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Search API returned {response.status}'
                    }
                    
        except Exception as e:
            self.logger.error(f"Error searching web: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def extract_urls_from_message(self, message: str) -> list:
        """Extract URLs from user message.
        
        Args:
            message: User message
            
        Returns:
            List of URLs found
        """
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, message)
        return urls
    
    def detect_search_intent(self, message: str) -> Optional[str]:
        """Detect if message contains search intent.
        
        Args:
            message: User message
            
        Returns:
            Search query if detected, None otherwise
        """
        message_lower = message.lower()
        
        # Search keywords
        search_keywords = ['search', 'find', 'look up', 'google', 'what is', 'who is', 'where is']
        
        for keyword in search_keywords:
            if keyword in message_lower:
                # Extract query after keyword
                parts = message_lower.split(keyword, 1)
                if len(parts) > 1:
                    query = parts[1].strip()
                    # Remove common question words
                    query = re.sub(r'^(for|about|on)\s+', '', query)
                    if query:
                        return query
        
        return None
    
    async def cleanup(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.logger.info("✅ Web scraper session closed")
    
    def format_web_content_for_ai(self, web_data: dict) -> str:
        """Format web content for inclusion in AI prompt.
        
        Args:
            web_data: Web scraping results
            
        Returns:
            Formatted string for AI prompt
        """
        formatted = "\n\nWEB CONTENT:\n"
        
        if web_data.get('success'):
            formatted += f"\nURL: {web_data['url']}\n"
            formatted += f"Title: {web_data.get('title', 'Unknown')}\n"
            
            if web_data.get('description'):
                formatted += f"Description: {web_data['description']}\n"
            
            formatted += f"\nContent:\n{web_data.get('content', '')}\n"
            
            if web_data.get('full_length', 0) > 5000:
                formatted += f"\n(Content truncated - full length: {web_data['full_length']} chars)\n"
        else:
            formatted += f"\nError fetching {web_data.get('url', 'URL')}: {web_data.get('error', 'Unknown error')}\n"
        
        return formatted
    
    def format_search_results_for_ai(self, search_data: dict) -> str:
        """Format search results for inclusion in AI prompt.
        
        Args:
            search_data: Search results
            
        Returns:
            Formatted string for AI prompt
        """
        formatted = "\n\nWEB SEARCH RESULTS:\n"
        
        if search_data.get('success'):
            formatted += f"\nQuery: {search_data['query']}\n"
            
            if search_data.get('abstract'):
                formatted += f"\nSummary: {search_data['abstract']}\n"
                if search_data.get('abstract_url'):
                    formatted += f"Source: {search_data['abstract_url']}\n"
            
            results = search_data.get('results', [])
            if results:
                formatted += f"\nTop {len(results)} Results:\n"
                for i, result in enumerate(results, 1):
                    formatted += f"\n{i}. {result.get('text', '')}\n"
                    if result.get('url'):
                        formatted += f"   URL: {result['url']}\n"
        else:
            formatted += f"\nSearch failed: {search_data.get('error', 'Unknown error')}\n"
        
        return formatted
