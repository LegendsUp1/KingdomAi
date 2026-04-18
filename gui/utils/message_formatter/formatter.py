"""
Message formatter implementation for the Thoth AI Qt chat interface.

This module handles the core formatting logic for different message types
with support for markdown, code blocks, files, and more.
"""

import re
import html
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Union, Pattern, Callable, Match

# Type aliases
HtmlString = str

class MessageFormatter:
    """Handles formatting of different message types in the chat interface."""
    
    # Regular expressions for different message patterns
    URL_PATTERN: Pattern = re.compile(
        r'\b(https?://|www\.)[^\s<>"]+[^\s<>",.;:\\\'"]',
        re.IGNORECASE
    )
    MENTION_PATTERN: Pattern = re.compile(r'(?<!\w)@(\w+)')
    CODE_BLOCK_PATTERN: Pattern = re.compile(r'```(?:\w*\n)?([\s\S]*?)```')
    INLINE_CODE_PATTERN: Pattern = re.compile(r'`([^`]+)`')
    BOLD_PATTERN: Pattern = re.compile(r'\*\*(.*?)\*\*')
    ITALIC_PATTERN: Pattern = re.compile(r'\*(.*?)\*')
    STRIKETHROUGH_PATTERN: Pattern = re.compile(r'~~(.*?)~~')
    
    @classmethod
    def format_message(
        cls,
        text: str,
        message_type: str = 'text',
        sender: str = '',
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> HtmlString:
        """Format a message with appropriate styling based on its type.
        
        Args:
            text: The message text to format
            message_type: Type of message ('text', 'code', 'image', 'file', 'system')
            sender: Name of the message sender
            timestamp: When the message was sent
            metadata: Additional message metadata
            
        Returns:
            Formatted HTML string for the message
        """
        if not text and message_type == 'text':
            return ''
            
        # Handle timestamp - can be string or datetime
        if isinstance(timestamp, str):
            time_str = timestamp
        elif timestamp is None:
            time_str = datetime.now().strftime('%H:%M')
        else:
            time_str = timestamp.strftime('%H:%M')
        
        # Process different message types
        if message_type == 'code':
            return cls._format_code_message(text, sender, time_str, metadata or {})
        elif message_type == 'image':
            return cls._format_image_message(text, sender, time_str, metadata or {})
        elif message_type == 'file':
            return cls._format_file_message(text, sender, time_str, metadata or {})
        elif message_type == 'system':
            return cls._format_system_message(text, time_str, metadata or {})
        else:
            return cls._format_text_message(text, sender, time_str, metadata or {})
    
    @classmethod
    def _format_text_message(
        cls,
        text: str,
        sender: str,
        time_str: str,
        metadata: Dict[str, Any]
    ) -> HtmlString:
        """Format a standard text message with markdown support."""
        # Escape HTML to prevent XSS
        text = html.escape(text)
        
        # Process markdown-like syntax
        text = cls._process_markdown(text)
        
        # Process URLs
        text = cls._process_urls(text)
        
        # Process mentions
        text = cls._process_mentions(text)
        
        # Get bubble style based on sender
        bubble_style = (
            'user-message' if metadata.get('is_user', False)
            else 'ai-message'
        )
        
        # Format the message with HTML
        return f"""
        <div class="message {bubble_style}" data-sender="{html.escape(sender)}" data-time="{time_str}">
            <div class="message-header">
                <span class="message-sender">{html.escape(sender)}</span>
                <span class="message-time">{time_str}</span>
            </div>
            <div class="message-content">
                {text}
            </div>
            {cls._get_message_footer(metadata)}
        </div>
        """
    
    @classmethod
    def _format_code_message(
        cls,
        code: str,
        sender: str,
        time_str: str,
        metadata: Dict[str, Any]
    ) -> HtmlString:
        """Format a code block message with syntax highlighting."""
        language = metadata.get('language', '')
        
        # Get bubble style based on sender
        bubble_style = (
            'user-message' if metadata.get('is_user', False)
            else 'ai-message'
        )
        
        # Format the code block
        return f"""
        <div class="message {bubble_style} code-message" data-sender="{html.escape(sender)}" data-time="{time_str}">
            <div class="message-header">
                <span class="message-sender">{html.escape(sender)}</span>
                <span class="message-time">{time_str}</span>
                {f'<span class="code-language">{html.escape(language)}</span>' if language else ''}
                <button class="copy-code-button" onclick="copyCodeToClipboard(this)">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                    Copy
                </button>
            </div>
            <div class="message-content code-block">
                <pre><code class="language-{html.escape(language)}">{html.escape(code)}</code></pre>
            </div>
            {cls._get_message_footer(metadata)}
        </div>
        """
    
    @classmethod
    def _format_image_message(
        cls,
        image_url: str,
        sender: str,
        time_str: str,
        metadata: Dict[str, Any]
    ) -> HtmlString:
        """Format an image message with preview and expand functionality."""
        alt_text = metadata.get('alt_text', 'Image')
        
        # Get bubble style based on sender
        bubble_style = (
            'user-message' if metadata.get('is_user', False)
            else 'ai-message'
        )
        
        return f"""
        <div class="message {bubble_style} image-message" data-sender="{html.escape(sender)}" data-time="{time_str}">
            <div class="message-header">
                <span class="message-sender">{html.escape(sender)}</span>
                <span class="message-time">{time_str}</span>
            </div>
            <div class="message-content">
                <div class="image-container" onclick="expandImage(this)">
                    <img src="{html.escape(image_url)}" alt="{html.escape(alt_text)}" loading="lazy">
                    <div class="image-overlay">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"></path>
                        </svg>
                    </div>
                </div>
                {f'<div class="image-caption">{html.escape(alt_text)}</div>' if alt_text else ''}
            </div>
            {cls._get_message_footer(metadata)}
        </div>
        """
    
    @classmethod
    def _format_file_message(
        cls,
        file_url: str,
        sender: str,
        time_str: str,
        metadata: Dict[str, Any]
    ) -> HtmlString:
        """Format a file attachment message with icon and download button."""
        file_name = metadata.get('file_name', 'file')
        file_size = metadata.get('file_size', '')
        file_type = metadata.get('file_type', '')
        
        # Get file icon based on file type
        file_icon = cls._get_file_icon(file_type)
        
        # Get bubble style based on sender
        bubble_style = (
            'user-message' if metadata.get('is_user', False)
            else 'ai-message'
        )
        
        return f"""
        <div class="message {bubble_style} file-message" data-sender="{html.escape(sender)}" data-time="{time_str}">
            <div class="message-header">
                <span class="message-sender">{html.escape(sender)}</span>
                <span class="message-time">{time_str}</span>
            </div>
            <div class="message-content">
                <div class="file-container">
                    <div class="file-icon">
                        {file_icon}
                    </div>
                    <div class="file-info">
                        <div class="file-name">{html.escape(file_name)}</div>
                        {f'<div class="file-meta">{html.escape(file_size)} • {html.escape(file_type)}</div>' if file_size or file_type else ''}
                    </div>
                    <a href="{html.escape(file_url)}" class="download-button" download>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="7 10 12 15 17 10"></polyline>
                            <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                    </a>
                </div>
            </div>
            {cls._get_message_footer(metadata)}
        </div>
        """
    
    @classmethod
    def _format_system_message(
        cls,
        text: str,
        time_str: str,
        metadata: Dict[str, Any]
    ) -> HtmlString:
        """Format a system message with appropriate styling."""
        # Escape HTML to prevent XSS
        text = html.escape(text)
        
        # Process markdown-like syntax
        text = cls._process_markdown(text)
        
        # Process URLs
        text = cls._process_urls(text)
        
        return f"""
        <div class="message system-message" data-time="{time_str}">
            <div class="message-content">
                {text}
            </div>
        </div>
        """
    
    @classmethod
    def _get_message_footer(cls, metadata: Dict[str, Any]) -> HtmlString:
        """Generate message footer with actions and status."""
        actions = []
        
        # Add copy button if not a system message
        if metadata.get('show_actions', True):
            actions.append("""
            <button class="message-action" onclick="copyMessage(this)" title="Copy">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
            </button>
            """)
            
            # Add reply button if enabled
            if metadata.get('allow_reply', True):
                actions.append("""
                <button class="message-action" onclick="replyToMessage(this)" title="Reply">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="9 10 4 15 9 20"></polyline>
                        <path d="M20 4v7a4 4 0 0 1-4 4H4"></path>
                    </svg>
                </button>
                """)
            
            # Add reactions if enabled
            if metadata.get('allow_reactions', True):
                reactions = ""
                for emoji in ["👍", "❤️", "😮", "😄", "🙁"]:
                    reactions += f"""
                    <button class="reaction-button" onclick="addReaction(this, '{emoji}')">
                        {emoji} <span class="reaction-count">0</span>
                    </button>
                    """
                
                actions.append(f"""
                <div class="reactions-container">
                    <div class="reactions">
                        {reactions}
                    </div>
                    <button class="add-reaction" onclick="showReactionPicker(this)" title="Add reaction">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 5v14M5 12h14"></path>
                        </svg>
                    </button>
                </div>
                """)
        
        # Add status indicator (read receipts, etc.)
        status = ''
        if 'status' in metadata:
            status_icon = {
                'sending': '⏳',
                'sent': '✓',
                'delivered': '✓✓',
                'read': '✓✓✓',
                'error': '⚠️'
            }.get(metadata['status'], '')
            
            if status_icon:
                status = f'<div class="message-status">{status_icon}</div>'
        
        if actions or status:
            return f"""
            <div class="message-footer">
                <div class="message-actions">
                    {"".join(actions)}
                </div>
                {status}
            </div>
            """
        return ''
    
    @classmethod
    def _process_markdown(cls, text: str) -> str:
        """Process markdown-like syntax in the text."""
        # Bold: **text**
        text = cls.BOLD_PATTERN.sub(r'<strong>\1</strong>', text)
        
        # Italic: *text*
        text = cls.ITALIC_PATTERN.sub(r'<em>\1</em>', text)
        
        # Strikethrough: ~~text~~
        text = cls.STRIKETHROUGH_PATTERN.sub(r'<s>\1</s>', text)
        
        # Inline code: `code`
        text = cls.INLINE_CODE_PATTERN.sub(
            r'<code class="inline-code">\1</code>', text
        )
        
        # Code blocks: ```[language]
        # code
        # ```
        text = cls.CODE_BLOCK_PATTERN.sub(
            lambda m: f'<pre><code class="code-block">{html.escape(m.group(1))}</code></pre>',
            text
        )
        
        # Headers: # Header 1, ## Header 2, etc.
        text = re.sub(r'^#\s+(.+?)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
        text = re.sub(r'^##\s+(.+?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^###\s+(.+?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        
        # Lists: - item or * item
        text = re.sub(r'^[\*\-]\s+(.+?)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', text, flags=re.DOTALL)
        
        # Blockquotes: > quote
        text = re.sub(r'^>\s+(.+?)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
        
        # Horizontal rule: --- or ***
        text = re.sub(r'^[-\*]{3,}$', '<hr>', text, flags=re.MULTILINE)
        
        # Preserve line breaks
        text = text.replace('\n', '<br>')
        
        return text
    
    @classmethod
    def _process_urls(cls, text: str) -> str:
        """Convert URLs to clickable links."""
        def make_link(match: Match) -> str:
            url = match.group(0)
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            return f'<a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">{html.escape(match.group(0))}</a>'
        
        return cls.URL_PATTERN.sub(make_link, text)
    
    @classmethod
    def _process_mentions(cls, text: str) -> str:
        """Convert @mentions to styled spans."""
        return cls.MENTION_PATTERN.sub(
            r'<span class="mention">@\1</span>',
            text
        )
    
    @classmethod
    def _get_file_icon(cls, file_type: str) -> str:
        """Get an appropriate icon for a file type."""
        file_type = file_type.lower()
        
        # Common document types
        if any(ext in file_type for ext in ['pdf']):
            return """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            """
        
        # Image types
        elif any(ext in file_type for ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']):
            return """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
            """
        
        # Archive types
        elif any(ext in file_type for ext in ['zip', 'rar', '7z', 'tar', 'gz']):
            return """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                <line x1="12" y1="22.08" x2="12" y2="12"></line>
            </svg>
            """
        
        # Audio types
        elif any(ext in file_type for ext in ['mp3', 'wav', 'ogg', 'm4a']):
            return """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 18V5l12-2v13"></path>
                <circle cx="6" cy="18" r="3"></circle>
                <circle cx="18" cy="16" r="3"></circle>
            </svg>
            """
        
        # Video types
        elif any(ext in file_type for ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']):
            return """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="23 7 16 12 23 17 23 7"></polygon>
                <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
            </svg>
            """
        
        # Default file icon
        return """
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
        </svg>
        """
