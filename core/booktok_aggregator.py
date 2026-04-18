#!/usr/bin/env python3
"""
Kingdom AI - BookTok Aggregator Alias
Provides backward compatibility import for BookTokAggregator
"""

# Import from the main module
from core.booktok_context_aggregator import (
    BookTokContextAggregator,
    get_booktok_aggregator
)

# Alias for backward compatibility
BookTokAggregator = BookTokContextAggregator

__all__ = ['BookTokAggregator', 'BookTokContextAggregator', 'get_booktok_aggregator']
