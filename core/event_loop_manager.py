#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Event Loop Manager Component

Provides centralized management of asyncio event loops to ensure proper
initialization, task creation, and cleanup during system shutdown.
"""

import asyncio
import logging
import threading
from typing import Optional, Set, Coroutine, Any

logger = logging.getLogger("KingdomAI.EventLoopManager")

class EventLoopManager:
    """Singleton manager for asyncio event loops.
    
    Ensures consistent event loop access and management across the system,
    with proper handling for multi-threaded environments and shutdown.
    """
    
    _instance = None
    _lock = threading.RLock()
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _tasks: Set[asyncio.Task] = set()
    
    def __new__(cls):
        """Ensure singleton pattern for the manager."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventLoopManager, cls).__new__(cls)
                # Initialize if running in main thread
                try:
                    cls._loop = asyncio.get_event_loop()
                except RuntimeError:
                    # Create a new event loop if there isn't one
                    cls._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(cls._loop)
                logger.info("EventLoopManager initialized")
        return cls._instance
    
    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Get the current event loop.
        
        Returns:
            asyncio.AbstractEventLoop: The managed event loop
        """
        return self._loop
    
    def run_until_complete(self, coro: Coroutine) -> Any:
        """Run a coroutine until completion.
        
        Args:
            coro: Coroutine to run
            
        Returns:
            Any: The result of the coroutine
        """
        return self._loop.run_until_complete(coro)
    
    def create_task(self, coro: Coroutine) -> asyncio.Task:
        """Create a task in the event loop and track it.
        
        Args:
            coro: Coroutine to create a task for
            
        Returns:
            asyncio.Task: The created task
        """
        task = self._loop.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(lambda t: self._tasks.discard(t))
        return task
    
    async def cancel_all_tasks(self) -> None:
        """Cancel all tracked tasks."""
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"Cancelled {len(tasks)} tracked tasks")
    
    def close(self) -> None:
        """Close the event loop safely."""
        try:
            # Cancel all running tasks
            if self._loop.is_running():
                # If the loop is running, we need to schedule cancellation
                asyncio.run_coroutine_threadsafe(self.cancel_all_tasks(), self._loop)
            else:
                # If the loop is not running, we can directly run the coroutine
                self._loop.run_until_complete(self.cancel_all_tasks())
            
            # Close the loop
            self._loop.close()
            logger.info("Event loop closed successfully")
        except Exception as e:
            logger.error(f"Error closing event loop: {e}")
    
    def get_or_create_loop_for_thread(self) -> asyncio.AbstractEventLoop:
        """Get an event loop for the current thread or create one if needed.
        
        Returns:
            asyncio.AbstractEventLoop: An event loop for the current thread
        """
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
