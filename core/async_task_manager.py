#!/usr/bin/env python3
"""
2025 Async Task Manager for Kingdom AI
=====================================

Modern asyncio task lifecycle management with cross-version compatibility,
proper error handling, graceful shutdown, and task monitoring using
industry-standard patterns that work from Python 3.7+.

Based on 2025 state-of-the-art patterns from Elastic Blog and asyncio best practices.
"""

import asyncio
import logging
import functools
import signal
import sys
import time
from typing import Set, List, Dict, Any, Optional, Callable, Awaitable, Union, Coroutine
from enum import Enum

logger = logging.getLogger(__name__)


class AsyncTaskManager:
    """2025 Async Task Lifecycle Management - Simplified Cross-Version Compatible"""
    
    def __init__(self, max_concurrency=10):
        self._active_tasks: Set[asyncio.Task] = set()
        self._shutdown_requested = False
        self.logger = logger
        self.max_concurrency = max_concurrency
        
    def create_managed_task(self, coro: Union[Coroutine, Callable], name: str = None) -> asyncio.Task:
        """Create task with automatic lifecycle management"""
        if self._shutdown_requested:
            self.logger.warning(f"Ignoring task creation during shutdown: {name}")
            # Return a cancelled task
            task = asyncio.create_task(asyncio.sleep(0))
            task.cancel()
            return task
            
        # Handle both coroutines and callables
        if callable(coro) and not asyncio.iscoroutine(coro):
            try:
                actual_coro = coro()
            except Exception as e:
                self.logger.error(f"Error calling coroutine function: {e}")
                # Return completed task with error
                task = asyncio.create_task(asyncio.sleep(0))
                task.cancel()
                return task
        else:
            actual_coro = coro
            
        # Create the task
        try:
            task = asyncio.create_task(actual_coro)
            self._active_tasks.add(task)
            
            # Auto-cleanup on completion
            task.add_done_callback(self._cleanup_task)
            
            self.logger.debug(f"Created managed task: {name or 'unnamed'}")
            return task
        except Exception as e:
            self.logger.error(f"Error creating task: {e}")
            # Return cancelled task as fallback
            task = asyncio.create_task(asyncio.sleep(0))
            task.cancel()
            return task
    
    def _cleanup_task(self, task: asyncio.Task):
        """Clean up completed tasks with proper error handling"""
        try:
            # Remove from active tasks
            self._active_tasks.discard(task)
            
            if task.cancelled():
                self.logger.debug(f"Task cancelled")
            elif task.exception():
                self.logger.error(f"Task failed: {task.exception()}")
            else:
                self.logger.debug(f"Task completed successfully")
                    
        except Exception as e:
            self.logger.error(f"Error during task cleanup: {e}")
    
    async def wait_for_tasks(self, timeout: float = 30.0) -> bool:
        """Wait for all active tasks to complete with timeout"""
        if not self._active_tasks:
            return True
            
        self.logger.info(f"Waiting for {len(self._active_tasks)} active tasks to complete...")
        
        try:
            # Wait for all tasks with timeout using gather with return_exceptions=True
            await asyncio.wait_for(
                asyncio.gather(*list(self._active_tasks), return_exceptions=True),
                timeout=timeout
            )
            self.logger.info("All tasks completed successfully")
            return True
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout waiting for tasks to complete after {timeout}s")
            return False
        except Exception as e:
            self.logger.error(f"Error waiting for tasks: {e}")
            return False
    
    async def cancel_all_tasks(self, grace_period: float = 5.0):
        """Cancel all active tasks with grace period"""
        if not self._active_tasks:
            return
            
        self.logger.info(f"Cancelling {len(self._active_tasks)} active tasks...")
        
        # Cancel all tasks
        for task in list(self._active_tasks):
            if not task.done():
                task.cancel()
        
        # Give tasks a chance to handle cancellation gracefully
        if grace_period > 0:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*list(self._active_tasks), return_exceptions=True),
                    timeout=grace_period
                )
            except asyncio.TimeoutError:
                self.logger.warning(f"Some tasks didn't respect cancellation grace period of {grace_period}s")
    
    async def shutdown_gracefully(self, timeout: float = 30.0) -> bool:
        """2025 Graceful Shutdown Pattern with proper cleanup"""
        self.logger.info("Initiating graceful shutdown of AsyncTaskManager...")
        self._shutdown_requested = True
        
        try:
            # Try to let tasks complete naturally
            if await self.wait_for_tasks(timeout=timeout/2):
                self.logger.info("All tasks completed during graceful shutdown")
                return True
            
            # If timeout, cancel remaining tasks
            self.logger.info("Timeout reached, cancelling remaining tasks...")
            await self.cancel_all_tasks(grace_period=timeout/2)
            
            # Clear tracking structures
            self._active_tasks.clear()
            
            self.logger.info("AsyncTaskManager shutdown completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during graceful shutdown: {e}")
            return False
    
    def get_task_stats(self) -> Dict[str, Any]:
        """Get statistics about managed tasks"""
        return {
            'active_tasks': len(self._active_tasks),
            'shutdown_requested': self._shutdown_requested,
            'max_concurrency': self.max_concurrency
        }


# Global task manager instance
_global_task_manager: Optional[AsyncTaskManager] = None

def get_global_task_manager() -> AsyncTaskManager:
    """Get or create the global task manager instance"""
    global _global_task_manager
    if _global_task_manager is None:
        _global_task_manager = AsyncTaskManager()
        logger.info("Created global AsyncTaskManager instance")
    return _global_task_manager


async def safe_create_task(coro: Union[Coroutine, Callable], name: str = None) -> asyncio.Task:
    """Convenience function to create managed tasks"""
    task_manager = get_global_task_manager()
    return task_manager.create_managed_task(coro, name)
