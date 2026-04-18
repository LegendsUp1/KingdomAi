#!/usr/bin/env python3
"""
Kingdom AI - Book Data Manager
Manages book data for BookTok video generation including database, APIs, and web scraping.
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger("KingdomAI.BookDataManager")


def _is_wsl2() -> bool:
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except Exception:
        return False

class BookDataManager:
    """Manages book data from multiple sources for BookTok generation."""
    
    def __init__(self, event_bus=None):
        """Initialize the Book Data Manager.
        
        Args:
            event_bus: System event bus for communication
        """
        self.event_bus = event_bus
        self.logger = logger
        
        # Database path
        self.db_path = Path("data") / "books.db"
        # WSL2 FIX: SQLite on /mnt/c (NTFS via 9P) has broken file locking
        if _is_wsl2() and str(self.db_path.resolve()).startswith('/mnt/'):
            self.db_path = Path.home() / '.kingdom_ai' / 'books.db'
            logger.info(f"WSL2 detected: using Linux-native path for SQLite: {self.db_path}")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # API endpoints
        self.apis = {
            'google_books': 'https://www.googleapis.com/books/v1/volumes',
            'open_library': 'https://openlibrary.org',
            'goodreads': 'https://www.goodreads.com'  # Requires API key
        }
        
        # Cache for recent lookups
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour
        
        # User's book library
        self.user_library = []
        self.trending_books = []
        
        # Initialize database
        self._init_database()
        
        # Subscribe to events
        if self.event_bus:
            self._subscribe_to_events()
    
    def _init_database(self):
        """Initialize the book database with proper schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Books table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                isbn PRIMARY KEY,
                title TEXT NOT NULL,
                subtitle TEXT,
                author TEXT NOT NULL,
                publisher TEXT,
                published_date TEXT,
                description TEXT,
                page_count INTEGER,
                categories TEXT,
                language TEXT,
                cover_url TEXT,
                rating REAL,
                ratings_count INTEGER,
                preview_link TEXT,
                info_link TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Authors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS authors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                bio TEXT,
                image_url TEXT,
                website TEXT,
                goodreads_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Genres/Categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                parent_genre_id INTEGER,
                FOREIGN KEY (parent_genre_id) REFERENCES genres(id)
            )
        ''')
        
        # User library table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT NOT NULL,
                status TEXT DEFAULT 'want_to_read',  -- want_to_read, reading, read
                rating INTEGER,
                review TEXT,
                notes TEXT,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_started TEXT,
                date_finished TEXT,
                reading_progress REAL DEFAULT 0,
                FOREIGN KEY (isbn) REFERENCES books(isbn)
            )
        ''')
        
        # Quotes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT NOT NULL,
                quote TEXT NOT NULL,
                page_number INTEGER,
                chapter TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (isbn) REFERENCES books(isbn)
            )
        ''')
        
        # Reviews table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT NOT NULL,
                reviewer_name TEXT,
                rating INTEGER,
                review_text TEXT,
                review_date TEXT,
                source TEXT,  -- goodreads, amazon, google, user
                helpful_count INTEGER DEFAULT 0,
                verified_purchase BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (isbn) REFERENCES books(isbn)
            )
        ''')
        
        # Trending books table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trending_books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT NOT NULL,
                platform TEXT,  -- tiktok, instagram, goodreads, amazon
                rank INTEGER,
                trend_date DATE,
                hashtags TEXT,
                views INTEGER,
                likes INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (isbn) REFERENCES books(isbn),
                UNIQUE(isbn, platform, trend_date)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Book database initialized with full schema")
    
    def _subscribe_to_events(self):
        """Subscribe to book-related events."""
        self.event_bus.subscribe_sync('book.search', self._handle_book_search)
        self.event_bus.subscribe_sync('book.add_to_library', self._handle_add_to_library)
        self.event_bus.subscribe_sync('book.update_progress', self._handle_update_progress)
        self.event_bus.subscribe_sync('book.fetch_trending', self._handle_fetch_trending)
        self.event_bus.subscribe_sync('booktok.request_book_data', self._handle_booktok_request)
    
    async def search_book(self, query: str, source: str = 'google') -> List[Dict[str, Any]]:
        """Search for books across multiple sources.
        
        Args:
            query: Search query (title, author, ISBN)
            source: Data source ('google', 'openlibrary', 'all')
            
        Returns:
            List of book dictionaries
        """
        # Check cache first
        cache_key = f"{source}:{query}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_ttl:
                return cached['data']
        
        results = []
        
        if source in ['google', 'all']:
            google_results = await self._search_google_books(query)
            results.extend(google_results)
        
        if source in ['openlibrary', 'all']:
            ol_results = await self._search_open_library(query)
            results.extend(ol_results)
        
        # Cache results
        self.cache[cache_key] = {
            'data': results,
            'timestamp': time.time()
        }
        
        # Store in database
        for book in results:
            self._store_book(book)
        
        return results
    
    async def _search_google_books(self, query: str) -> List[Dict[str, Any]]:
        """Search Google Books API."""
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'q': query,
                    'maxResults': 10,
                    'printType': 'books'
                }
                
                async with session.get(self.apis['google_books'], params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        books = []
                        
                        for item in data.get('items', []):
                            volume = item.get('volumeInfo', {})
                            book = {
                                'isbn': self._extract_isbn(volume.get('industryIdentifiers', [])),
                                'title': volume.get('title', ''),
                                'subtitle': volume.get('subtitle', ''),
                                'authors': volume.get('authors', []),
                                'publisher': volume.get('publisher', ''),
                                'published_date': volume.get('publishedDate', ''),
                                'description': volume.get('description', ''),
                                'page_count': volume.get('pageCount', 0),
                                'categories': volume.get('categories', []),
                                'language': volume.get('language', ''),
                                'cover_url': volume.get('imageLinks', {}).get('thumbnail', ''),
                                'rating': volume.get('averageRating', 0),
                                'ratings_count': volume.get('ratingsCount', 0),
                                'preview_link': volume.get('previewLink', ''),
                                'info_link': volume.get('infoLink', ''),
                                'source': 'google_books'
                            }
                            books.append(book)
                        
                        return books
        except Exception as e:
            logger.error(f"Google Books API error: {e}")
        return []
    
    async def _search_open_library(self, query: str) -> List[Dict[str, Any]]:
        """Search Open Library API."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.apis['open_library']}/search.json"
                params = {
                    'q': query,
                    'limit': 10
                }
                
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        books = []
                        
                        for doc in data.get('docs', []):
                            book = {
                                'isbn': doc.get('isbn', [''])[0] if doc.get('isbn') else '',
                                'title': doc.get('title', ''),
                                'subtitle': doc.get('subtitle', ''),
                                'authors': [doc.get('author_name', [''])[0]] if doc.get('author_name') else [],
                                'publisher': ', '.join(doc.get('publisher', [])),
                                'published_date': str(doc.get('first_publish_year', '')),
                                'description': doc.get('first_sentence', [''])[0] if doc.get('first_sentence') else '',
                                'page_count': doc.get('number_of_pages_median', 0),
                                'categories': doc.get('subject', [])[:5] if doc.get('subject') else [],
                                'language': ', '.join(doc.get('language', [])),
                                'cover_url': f"https://covers.openlibrary.org/b/id/{doc.get('cover_i', '')}-M.jpg" if doc.get('cover_i') else '',
                                'rating': doc.get('ratings_average', 0),
                                'ratings_count': doc.get('ratings_count', 0),
                                'source': 'open_library'
                            }
                            books.append(book)
                        
                        return books
        except Exception as e:
            logger.error(f"Open Library API error: {e}")
        return []
    
    async def scrape_goodreads_trending(self) -> List[Dict[str, Any]]:
        """Scrape trending books from Goodreads (example implementation)."""
        trending = []
        try:
            async with aiohttp.ClientSession() as session:
                # This would require proper web scraping implementation
                # For now, return sample data
                trending = [
                    {
                        'title': 'Fourth Wing',
                        'author': 'Rebecca Yarros',
                        'isbn': '9781649374042',
                        'rating': 4.5,
                        'trending_rank': 1,
                        'platform': 'goodreads',
                        'hashtags': ['#FourthWing', '#BookTok', '#RomanceFantasy']
                    },
                    {
                        'title': 'Happy Place',
                        'author': 'Emily Henry',
                        'isbn': '9780593441275',
                        'rating': 4.3,
                        'trending_rank': 2,
                        'platform': 'goodreads',
                        'hashtags': ['#HappyPlace', '#BookTok', '#BeachRead']
                    }
                ]
                
                # Store trending books
                for book in trending:
                    self._store_trending_book(book)
                
        except Exception as e:
            logger.error(f"Goodreads scraping error: {e}")
        
        return trending
    
    def _store_book(self, book_data: Dict[str, Any]):
        """Store book data in database."""
        if not book_data.get('isbn'):
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO books (
                    isbn, title, subtitle, author, publisher, published_date,
                    description, page_count, categories, language, cover_url,
                    rating, ratings_count, preview_link, info_link, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                book_data.get('isbn'),
                book_data.get('title'),
                book_data.get('subtitle'),
                ', '.join(book_data.get('authors', [])) if isinstance(book_data.get('authors'), list) else book_data.get('authors'),
                book_data.get('publisher'),
                book_data.get('published_date'),
                book_data.get('description'),
                book_data.get('page_count'),
                json.dumps(book_data.get('categories', [])),
                book_data.get('language'),
                book_data.get('cover_url'),
                book_data.get('rating'),
                book_data.get('ratings_count'),
                book_data.get('preview_link'),
                book_data.get('info_link')
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error storing book: {e}")
        finally:
            conn.close()
    
    def _store_trending_book(self, trending_data: Dict[str, Any]):
        """Store trending book data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # First ensure the book exists
            self._store_book(trending_data)
            
            # Then store trending info
            cursor.execute('''
                INSERT OR REPLACE INTO trending_books (
                    isbn, platform, rank, trend_date, hashtags, views, likes
                ) VALUES (?, ?, ?, DATE('now'), ?, ?, ?)
            ''', (
                trending_data.get('isbn'),
                trending_data.get('platform', 'unknown'),
                trending_data.get('trending_rank', 999),
                json.dumps(trending_data.get('hashtags', [])),
                trending_data.get('views', 0),
                trending_data.get('likes', 0)
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error storing trending book: {e}")
        finally:
            conn.close()
    
    def _extract_isbn(self, identifiers: List[Dict[str, str]]) -> str:
        """Extract ISBN from industry identifiers."""
        for identifier in identifiers:
            if identifier.get('type') in ['ISBN_13', 'ISBN_10']:
                return identifier.get('identifier', '')
        return ''
    
    def get_user_library(self) -> List[Dict[str, Any]]:
        """Get user's book library from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ul.*, b.title, b.author, b.cover_url, b.rating
            FROM user_library ul
            JOIN books b ON ul.isbn = b.isbn
            ORDER BY ul.date_added DESC
        ''')
        
        library = []
        for row in cursor.fetchall():
            library.append({
                'isbn': row[1],
                'title': row[10],
                'author': row[11],
                'cover_url': row[12],
                'status': row[2],
                'user_rating': row[3],
                'review': row[4],
                'notes': row[5],
                'reading_progress': row[9]
            })
        
        conn.close()
        return library
    
    def get_book_quotes(self, isbn: str) -> List[Dict[str, Any]]:
        """Get quotes for a specific book."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT quote, page_number, chapter, source
            FROM quotes
            WHERE isbn = ?
        ''', (isbn,))
        
        quotes = []
        for row in cursor.fetchall():
            quotes.append({
                'quote': row[0],
                'page_number': row[1],
                'chapter': row[2],
                'source': row[3]
            })
        
        conn.close()
        return quotes
    
    def get_book_reviews(self, isbn: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get reviews for a specific book."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT reviewer_name, rating, review_text, review_date, source
            FROM reviews
            WHERE isbn = ?
            ORDER BY helpful_count DESC
            LIMIT ?
        ''', (isbn, limit))
        
        reviews = []
        for row in cursor.fetchall():
            reviews.append({
                'reviewer': row[0],
                'rating': row[1],
                'review': row[2],
                'date': row[3],
                'source': row[4]
            })
        
        conn.close()
        return reviews
    
    async def get_booktok_book_data(self, prompt: str = "") -> Dict[str, Any]:
        """Get book data specifically formatted for BookTok generation.
        
        Args:
            prompt: User's BookTok prompt that might contain book references
            
        Returns:
            Dictionary with book data ready for BookTok video generation
        """
        book_data = {
            'user_library': [],
            'trending_books': [],
            'featured_book': None,
            'quotes': [],
            'reviews': [],
            'hashtags': []
        }
        
        # Get user's library
        book_data['user_library'] = self.get_user_library()
        
        # Get trending books
        trending = await self.scrape_goodreads_trending()
        book_data['trending_books'] = trending
        
        # If prompt mentions a specific book, search for it
        if prompt:
            search_results = await self.search_book(prompt, source='all')
            if search_results:
                featured = search_results[0]
                book_data['featured_book'] = featured
                
                # Get quotes and reviews for featured book
                if featured.get('isbn'):
                    book_data['quotes'] = self.get_book_quotes(featured['isbn'])
                    book_data['reviews'] = self.get_book_reviews(featured['isbn'])
        
        # Generate BookTok hashtags
        book_data['hashtags'] = [
            '#BookTok',
            '#BookRecommendations',
            '#BookishContent',
            '#ReadingLife',
            '#BookCommunity'
        ]
        
        # Add trending hashtags
        for book in trending[:3]:
            book_data['hashtags'].extend(book.get('hashtags', []))
        
        return book_data
    
    # Event handlers
    def _handle_book_search(self, event_type: str, data: Dict[str, Any]):
        """Handle book search event."""
        query = data.get('query', '')
        asyncio.create_task(self.search_book(query))
    
    def _handle_add_to_library(self, event_type: str, data: Dict[str, Any]):
        """Handle adding book to user library."""
        isbn = data.get('isbn')
        if isbn:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO user_library (isbn, status)
                VALUES (?, 'want_to_read')
            ''', (isbn,))
            conn.commit()
            conn.close()
    
    def _handle_update_progress(self, event_type: str, data: Dict[str, Any]):
        """Handle reading progress update."""
        isbn = data.get('isbn')
        progress = data.get('progress', 0)
        if isbn:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE user_library
                SET reading_progress = ?, status = 'reading'
                WHERE isbn = ?
            ''', (progress, isbn))
            conn.commit()
            conn.close()
    
    def _handle_fetch_trending(self, event_type: str, data: Dict[str, Any]):
        """Handle fetch trending books event."""
        asyncio.create_task(self.scrape_goodreads_trending())
    
    def _handle_booktok_request(self, event_type: str, data: Dict[str, Any]):
        """Handle BookTok request for book data."""
        prompt = data.get('prompt', '')
        
        async def fetch_and_publish():
            book_data = await self.get_booktok_book_data(prompt)
            if self.event_bus:
                self.event_bus.publish('book.data.ready', book_data)
        
        asyncio.create_task(fetch_and_publish())

# Global singleton instance
_book_manager_instance = None

def get_book_manager(event_bus=None) -> BookDataManager:
    """Get or create the global book data manager instance."""
    global _book_manager_instance
    if _book_manager_instance is None:
        _book_manager_instance = BookDataManager(event_bus)
    return _book_manager_instance
