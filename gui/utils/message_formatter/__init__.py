"""
Message formatting utilities for the Thoth AI Qt chat interface.

This package provides functionality to format different types of chat messages
including text, code blocks, images, files, and system messages with
state-of-the-art styling and interactivity (2025 best practices).
"""

from .formatter import MessageFormatter
from .widgets import MessageWidget, MessageWidgetFactory

__all__ = ['MessageFormatter', 'MessageWidget', 'MessageWidgetFactory']
