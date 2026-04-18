#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Async Support Module for Kingdom AI

Provides async utilities and support functions for Kingdom AI.
"""

import asyncio
import logging
from typing import Any, Coroutine, Optional

logger = logging.getLogger(__name__)

class AsyncSupport:
    """Provides async utilities for Kingdom AI components."""
    
    def __init__(self):
        """Initialize async support."""
        self.loop = None
        logger.info("AsyncSupport initialized")
    
    def get_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.new_event_loop()
    
    async def run_async(self, coro: Coroutine) -> Any:
        """Run a coroutine safely."""
        try:
            return await coro
        except Exception as e:
            logger.error(f"Error running async task: {e}")
            raise
    
    def run_in_executor(self, func, *args, **kwargs):
        """Run a function in executor."""
        loop = self.get_event_loop()
        return loop.run_in_executor(None, func, *args, **kwargs)

# Global async support instance
async_support = AsyncSupport()

__all__ = ['AsyncSupport', 'async_support']
