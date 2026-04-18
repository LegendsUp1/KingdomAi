#!/usr/bin/env python3
"""
Kingdom AI - SOTA 2026 Multimodal Web Scraper
==============================================

Advanced web scraping with video, audio, image, and text extraction.
Integrates with Ollama brain for content analysis and learning.

Features:
- Video extraction and frame analysis
- Audio extraction and transcription
- Image extraction and analysis
- Text extraction with semantic understanding
- Content storage for learning and recall
- Fact correlation across all media types
"""

import os
import sys
import re
import json
import logging
import asyncio
import hashlib
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin

logger = logging.getLogger("KingdomAI.MultimodalWebScraper")

# Check dependencies
HAS_AIOHTTP = False
HAS_BS4 = False
HAS_YOUTUBE_DL = False
HAS_FFMPEG = False
HAS_PIL = False
HAS_WHISPER = False

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    logger.warning("aiohttp not available - async scraping disabled")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    logger.warning("BeautifulSoup not available - HTML parsing limited")

try:
    import yt_dlp
    HAS_YOUTUBE_DL = True
except ImportError:
    try:
        import youtube_dl
        HAS_YOUTUBE_DL = True
    except ImportError:
        HAS_YOUTUBE_DL = False
        logger.info("ℹ️ yt-dlp/youtube-dl not available - video extraction limited")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    logger.warning("PIL not available - image processing limited")

try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    logger.warning("Whisper not available - audio transcription disabled")

# Check FFmpeg
try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
    HAS_FFMPEG = result.returncode == 0
except Exception:
    HAS_FFMPEG = False
    logger.warning("FFmpeg not available - video/audio processing limited")


@dataclass
class ScrapedContent:
    """Container for scraped multimodal content."""
    url: str
    title: str
    text: str = ""
    images: List[Dict[str, Any]] = field(default_factory=list)
    videos: List[Dict[str, Any]] = field(default_factory=list)
    audio: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    content_hash: str = ""
    
    def __post_init__(self):
        """Generate content hash for deduplication."""
        if not self.content_hash:
            content_str = f"{self.url}{self.title}{self.text}"
            self.content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]


class MultimodalWebScraperSOTA2026:
    """SOTA 2026 Multimodal Web Scraper with Ollama integration."""
    
    def __init__(self, event_bus=None, ollama_learning=None, storage_dir: Optional[str] = None):
        """Initialize the multimodal web scraper.
        
        Args:
            event_bus: EventBus for publishing scraping events
            ollama_learning: OllamaLearningSystem for content analysis
            storage_dir: Directory for storing scraped content
        """
        self.event_bus = event_bus
        self.ollama_learning = ollama_learning
        self.storage_dir = storage_dir or str(Path(__file__).parent.parent / "data" / "scraped_content")
        
        # Create storage directories
        os.makedirs(self.storage_dir, exist_ok=True)
        os.makedirs(os.path.join(self.storage_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(self.storage_dir, "videos"), exist_ok=True)
        os.makedirs(os.path.join(self.storage_dir, "audio"), exist_ok=True)
        os.makedirs(os.path.join(self.storage_dir, "metadata"), exist_ok=True)
        
        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, ScrapedContent] = {}
        self.cache_timeout = 3600  # 1 hour
        
        # Whisper model for transcription
        self.whisper_model = None
        
        logger.info(f"✅ SOTA 2026 Multimodal Web Scraper initialized (storage={self.storage_dir})")
        logger.info(f"   Available: aiohttp={HAS_AIOHTTP}, bs4={HAS_BS4}, yt-dlp={HAS_YOUTUBE_DL}")
        logger.info(f"   Available: ffmpeg={HAS_FFMPEG}, PIL={HAS_PIL}, whisper={HAS_WHISPER}")
    
    async def initialize(self) -> bool:
        """Initialize the scraper and HTTP session."""
        try:
            if HAS_AIOHTTP and not self.session:
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30)
                )
            
            # Load Whisper model if available
            if HAS_WHISPER and not self.whisper_model:
                try:
                    self.whisper_model = whisper.load_model("base")
                    logger.info("✅ Whisper model loaded for audio transcription")
                except Exception as e:
                    logger.warning(f"Failed to load Whisper model: {e}")
            
            # Subscribe to scraping events
            if self.event_bus:
                self.event_bus.subscribe("web.scrape", self._handle_scrape_request)
                self.event_bus.subscribe("web.scrape.video", self._handle_video_scrape)
                self.event_bus.subscribe("web.scrape.audio", self._handle_audio_scrape)
                self.event_bus.subscribe("web.scrape.images", self._handle_image_scrape)
                logger.info("✅ Subscribed to web scraping events")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize multimodal web scraper: {e}")
            return False
    
    async def scrape_url(self, url: str, extract_media: bool = True,
                        analyze_with_ollama: bool = True) -> ScrapedContent:
        """Scrape a URL and extract all multimodal content.
        
        Args:
            url: URL to scrape
            extract_media: Whether to extract images, videos, audio
            analyze_with_ollama: Whether to analyze content with Ollama
            
        Returns:
            ScrapedContent object with all extracted data
        """
        logger.info(f"🌐 Scraping URL: {url}")
        
        # Check cache
        if url in self.cache:
            cache_entry = self.cache[url]
            age = (datetime.now() - datetime.fromisoformat(cache_entry.timestamp)).total_seconds()
            if age < self.cache_timeout:
                logger.info(f"✅ Returning cached content for {url}")
                return cache_entry
        
        try:
            # Initialize session if needed
            if not self.session and HAS_AIOHTTP:
                await self.initialize()
            
            # Fetch HTML
            html, status = await self._fetch_html(url)
            if status != 200:
                return ScrapedContent(url=url, title="Error", text=f"HTTP {status}")
            
            # Parse HTML
            soup = BeautifulSoup(html, 'html.parser') if HAS_BS4 else None
            
            # Extract text content
            text = self._extract_text(soup, html)
            title = self._extract_title(soup, html)
            
            # Create content object
            content = ScrapedContent(
                url=url,
                title=title,
                text=text,
                metadata={'status': status, 'content_length': len(html)}
            )
            
            # Extract media if requested
            if extract_media and soup:
                content.images = await self._extract_images(soup, url)
                content.videos = await self._extract_videos(soup, url)
                content.audio = await self._extract_audio(soup, url)
            
            # Analyze with Ollama if requested
            if analyze_with_ollama and self.ollama_learning:
                await self._analyze_with_ollama(content)
            
            # Store content
            await self._store_content(content)
            
            # Cache result
            self.cache[url] = content
            
            # Publish event
            if self.event_bus:
                self.event_bus.publish("web.scraped", {
                    "url": url,
                    "title": title,
                    "text_length": len(text),
                    "images_count": len(content.images),
                    "videos_count": len(content.videos),
                    "audio_count": len(content.audio),
                    "timestamp": content.timestamp
                })
            
            logger.info(f"✅ Scraped {url}: {len(text)} chars, {len(content.images)} images, {len(content.videos)} videos")
            return content
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return ScrapedContent(url=url, title="Error", text=str(e))
    
    async def _fetch_html(self, url: str) -> Tuple[str, int]:
        """Fetch HTML from URL."""
        if not self.session:
            return "", 0
        
        try:
            async with self.session.get(url) as response:
                html = await response.text()
                return html, response.status
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return "", 0
    
    def _extract_text(self, soup: Optional[BeautifulSoup], html: str) -> str:
        """Extract text content from HTML."""
        if not soup:
            # Fallback: strip HTML tags with regex
            text = re.sub(r'<[^>]+>', '', html)
            return text[:10000]  # Limit to 10k chars
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Extract text
        text = soup.get_text(separator='\n', strip=True)
        
        # Clean up whitespace
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        return text[:10000]  # Limit to 10k chars
    
    def _extract_title(self, soup: Optional[BeautifulSoup], html: str) -> str:
        """Extract page title."""
        if soup and soup.title:
            return soup.title.string or "No title"
        
        # Fallback: regex
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        return match.group(1) if match else "No title"
    
    async def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """Extract and download images from page."""
        images = []
        
        for img in soup.find_all('img')[:20]:  # Limit to 20 images
            src = img.get('src') or img.get('data-src')
            if not src:
                continue
            
            # Make absolute URL
            img_url = urljoin(base_url, src)
            
            # Download image
            img_path = await self._download_image(img_url)
            
            if img_path:
                # Analyze image with Ollama if available
                analysis = await self._analyze_image(img_path) if self.ollama_learning else ""
                
                images.append({
                    'url': img_url,
                    'local_path': img_path,
                    'alt': img.get('alt', ''),
                    'analysis': analysis
                })
        
        return images
    
    async def _download_image(self, url: str) -> Optional[str]:
        """Download image to storage."""
        if not self.session:
            return None
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    # Generate filename
                    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                    ext = Path(urlparse(url).path).suffix or '.jpg'
                    filename = f"img_{url_hash}{ext}"
                    filepath = os.path.join(self.storage_dir, "images", filename)
                    
                    # Save image
                    content = await response.read()
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    return filepath
        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")
        
        return None
    
    async def _extract_videos(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """Extract videos from page."""
        videos = []
        
        # Extract video tags
        for video in soup.find_all('video')[:5]:  # Limit to 5 videos
            sources = video.find_all('source')
            for source in sources:
                src = source.get('src')
                if src:
                    video_url = urljoin(base_url, src)
                    videos.append({
                        'url': video_url,
                        'type': 'html5_video',
                        'source': 'video_tag'
                    })
        
        # Extract YouTube/Vimeo embeds
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if 'youtube.com' in src or 'youtu.be' in src or 'vimeo.com' in src:
                videos.append({
                    'url': src,
                    'type': 'embedded_video',
                    'source': 'iframe'
                })
        
        # Download and analyze videos
        for video in videos[:3]:  # Limit processing to 3 videos
            video_path = await self._download_video(video['url'])
            if video_path:
                video['local_path'] = video_path
                video['analysis'] = await self._analyze_video(video_path)
        
        return videos
    
    async def _download_video(self, url: str) -> Optional[str]:
        """Download video using yt-dlp."""
        if not HAS_YOUTUBE_DL:
            return None
        
        try:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            output_path = os.path.join(self.storage_dir, "videos", f"video_{url_hash}.mp4")
            
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
                'max_filesize': 100 * 1024 * 1024,  # 100MB limit
            }
            
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            if os.path.exists(output_path):
                return output_path
                
        except Exception as e:
            logger.warning(f"Failed to download video {url}: {e}")
        
        return None
    
    async def _extract_audio(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """Extract audio from page."""
        audio_files = []
        
        # Extract audio tags
        for audio in soup.find_all('audio')[:5]:
            sources = audio.find_all('source')
            for source in sources:
                src = source.get('src')
                if src:
                    audio_url = urljoin(base_url, src)
                    audio_path = await self._download_audio(audio_url)
                    
                    if audio_path:
                        transcription = await self._transcribe_audio(audio_path)
                        audio_files.append({
                            'url': audio_url,
                            'local_path': audio_path,
                            'transcription': transcription
                        })
        
        return audio_files
    
    async def _download_audio(self, url: str) -> Optional[str]:
        """Download audio file."""
        if not self.session:
            return None
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                    ext = Path(urlparse(url).path).suffix or '.mp3'
                    filename = f"audio_{url_hash}{ext}"
                    filepath = os.path.join(self.storage_dir, "audio", filename)
                    
                    content = await response.read()
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    return filepath
        except Exception as e:
            logger.warning(f"Failed to download audio {url}: {e}")
        
        return None
    
    async def _transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio using Whisper."""
        if not HAS_WHISPER or not self.whisper_model:
            return ""
        
        try:
            result = self.whisper_model.transcribe(audio_path)
            return result.get('text', '')
        except Exception as e:
            logger.warning(f"Failed to transcribe audio: {e}")
            return ""
    
    async def _analyze_image(self, image_path: str) -> str:
        """Analyze image with Ollama."""
        if not self.ollama_learning:
            return ""
        
        try:
            from core.ollama_learning_integration import TaskType
            
            result = await self.ollama_learning.process(
                prompt="Describe this image in detail, including objects, colors, composition, and mood.",
                task_type=TaskType.IMAGE_ANALYSIS,
                images=[image_path],
                prefer_speed=True
            )
            
            return result.get('response', '')
        except Exception as e:
            logger.warning(f"Failed to analyze image: {e}")
            return ""
    
    async def _analyze_video(self, video_path: str) -> Dict[str, Any]:
        """Analyze video by extracting frames and analyzing with Ollama."""
        if not HAS_FFMPEG or not self.ollama_learning:
            return {}
        
        try:
            # Extract frames (1 frame per second, max 10 frames)
            frames_dir = tempfile.mkdtemp()
            frame_pattern = os.path.join(frames_dir, "frame_%03d.jpg")
            
            subprocess.run([
                'ffmpeg', '-i', video_path,
                '-vf', 'fps=1',
                '-frames:v', '10',
                frame_pattern
            ], capture_output=True, timeout=30)
            
            # Analyze frames
            frame_analyses = []
            for frame_file in sorted(Path(frames_dir).glob("*.jpg"))[:5]:
                analysis = await self._analyze_image(str(frame_file))
                if analysis:
                    frame_analyses.append(analysis)
            
            # Cleanup
            import shutil
            shutil.rmtree(frames_dir, ignore_errors=True)
            
            return {
                'frame_count': len(frame_analyses),
                'frame_analyses': frame_analyses,
                'summary': ' '.join(frame_analyses[:3])  # First 3 frames
            }
            
        except Exception as e:
            logger.warning(f"Failed to analyze video: {e}")
            return {}
    
    async def _analyze_with_ollama(self, content: ScrapedContent):
        """Analyze scraped content with Ollama for learning."""
        if not self.ollama_learning:
            return
        
        try:
            from core.ollama_learning_integration import TaskType
            
            # Analyze text content
            if content.text:
                result = await self.ollama_learning.process(
                    prompt=f"Analyze this web content and extract key facts, topics, and insights:\n\n{content.text[:2000]}",
                    task_type=TaskType.KNOWLEDGE_SYNTHESIS,
                    prefer_speed=False,
                    prefer_quality=True
                )
                
                content.metadata['ollama_analysis'] = result.get('response', '')
            
            # Store for learning
            if self.event_bus:
                self.event_bus.publish("learning.web_content", {
                    'url': content.url,
                    'title': content.title,
                    'text_preview': content.text[:500],
                    'analysis': content.metadata.get('ollama_analysis', ''),
                    'images_count': len(content.images),
                    'videos_count': len(content.videos),
                    'audio_count': len(content.audio)
                })
                
        except Exception as e:
            logger.warning(f"Failed to analyze content with Ollama: {e}")
    
    async def _store_content(self, content: ScrapedContent):
        """Store scraped content metadata."""
        try:
            metadata_file = os.path.join(
                self.storage_dir, "metadata",
                f"{content.content_hash}.json"
            )
            
            # Convert to dict
            content_dict = {
                'url': content.url,
                'title': content.title,
                'text': content.text,
                'images': content.images,
                'videos': content.videos,
                'audio': content.audio,
                'metadata': content.metadata,
                'timestamp': content.timestamp,
                'content_hash': content.content_hash
            }
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(content_dict, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.warning(f"Failed to store content metadata: {e}")
    
    # Event handlers
    async def _handle_scrape_request(self, data: Dict[str, Any]):
        """Handle web.scrape event."""
        url = data.get('url')
        if url:
            content = await self.scrape_url(
                url,
                extract_media=data.get('extract_media', True),
                analyze_with_ollama=data.get('analyze', True)
            )
            
            if self.event_bus:
                self.event_bus.publish("web.scrape.complete", {
                    'url': url,
                    'content': content,
                    'success': bool(content.text)
                })
    
    async def _handle_video_scrape(self, data: Dict[str, Any]):
        """Handle web.scrape.video event."""
        url = data.get('url')
        if url:
            video_path = await self._download_video(url)
            if video_path:
                analysis = await self._analyze_video(video_path)
                
                if self.event_bus:
                    self.event_bus.publish("web.scrape.video.complete", {
                        'url': url,
                        'local_path': video_path,
                        'analysis': analysis
                    })
    
    async def _handle_audio_scrape(self, data: Dict[str, Any]):
        """Handle web.scrape.audio event."""
        url = data.get('url')
        if url:
            audio_path = await self._download_audio(url)
            if audio_path:
                transcription = await self._transcribe_audio(audio_path)
                
                if self.event_bus:
                    self.event_bus.publish("web.scrape.audio.complete", {
                        'url': url,
                        'local_path': audio_path,
                        'transcription': transcription
                    })
    
    async def _handle_image_scrape(self, data: Dict[str, Any]):
        """Handle web.scrape.images event."""
        url = data.get('url')
        if url:
            # Scrape page for images
            content = await self.scrape_url(url, extract_media=True, analyze_with_ollama=False)
            
            if self.event_bus:
                self.event_bus.publish("web.scrape.images.complete", {
                    'url': url,
                    'images': content.images
                })
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None


# Global instance
_scraper: Optional[MultimodalWebScraperSOTA2026] = None


def get_multimodal_scraper(event_bus=None, ollama_learning=None) -> MultimodalWebScraperSOTA2026:
    """Get or create global scraper instance."""
    global _scraper
    if _scraper is None:
        _scraper = MultimodalWebScraperSOTA2026(event_bus, ollama_learning)
    return _scraper


__all__ = [
    'MultimodalWebScraperSOTA2026',
    'ScrapedContent',
    'get_multimodal_scraper',
]
