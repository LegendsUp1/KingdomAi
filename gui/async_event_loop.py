#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI Async Event Loop Integration Module

This module provides a seamless integration between asyncio and Qt/Tkinter event loops
using qasync or asyncio's event loop policies. It enables async/await coroutines to work
properly within GUI applications, preventing the "object not awaitable" errors.
"""

import asyncio
import logging
import sys
import os
from typing import Any, Callable, Coroutine, Optional, TypeVar, cast, Union
from functools import wraps

# Set up logging
logger = logging.getLogger(__name__)

# Define type variables
T = TypeVar('T')

# Detect environment and available packages
HAS_QASYNC = False
HAS_NEST_ASYNCIO = False

# Import qasync for Qt integration - preferred for Kingdom AI
try:
    import qasync
    HAS_QASYNC = True
    logger.info("qasync package is available for Qt-asyncio integration")
except ImportError as e:
    HAS_QASYNC = False
    logger.warning(f"qasync not available: {e} - async Qt integration will use fallback mode")
    logger.warning("Install qasync for best performance: pip install qasync")
    
# Try to import nest_asyncio for nested event loop support
try:
    import nest_asyncio
    HAS_NEST_ASYNCIO = True
    logger.info("nest_asyncio is available for nested event loop support")
except ImportError:
    logger.warning("nest_asyncio not available, nested event loops may cause issues")

# Check for Qt frameworks
HAS_PYQT6 = False
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    HAS_PYQT6 = True
    logger.info("PyQt6 detected")
except ImportError:
    logger.warning("PyQt6 not detected, falling back to other mechanisms")


class AsyncSupport:
    """Singleton class to manage async operations in a GUI environment."""
    
    _instance = None
    _initialized = False
    _event_loop = None
    _qt_app = None
    _using_qt = False
    _using_tkinter = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AsyncSupport, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if AsyncSupport._initialized:
            return
        
        self.logger = logging.getLogger(f"{__name__}.AsyncSupport")
        self._detect_environment()
        self._initialize_event_loop()
        AsyncSupport._initialized = True
        
    def _detect_environment(self):
        """Detect which GUI framework and event loop to use."""
        # Try to detect Qt first
        if HAS_PYQT6:
            AsyncSupport._using_qt = True
            self.logger.info("Using PyQt6 for async integration")
        else:
            # Check if we're in a Tkinter environment
            try:
                import tkinter as tk
                AsyncSupport._using_tkinter = True
                self.logger.info("Using Tkinter for async integration")
            except ImportError:
                self.logger.warning("No GUI framework detected")
    
    def _initialize_event_loop(self):
        """Initialize the appropriate event loop based on the environment."""
        try:
            # If using Qt with qasync available
            if AsyncSupport._using_qt and HAS_QASYNC:
                # Get existing QApplication instance if available
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app is None:
                    app = QApplication(sys.argv)
                AsyncSupport._qt_app = app
                
                # Create qasync loop
                AsyncSupport._event_loop = qasync.QEventLoop(app)
                asyncio.set_event_loop(AsyncSupport._event_loop)
                self.logger.info("Initialized qasync event loop with PyQt6")
                
            # For Tkinter or if qasync is not available
            else:
                # Get or create a standard asyncio event loop
                try:
                    AsyncSupport._event_loop = asyncio.get_event_loop()
                except RuntimeError:
                    AsyncSupport._event_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(AsyncSupport._event_loop)
                
                # Apply nest_asyncio if available for nested event loop support
                if HAS_NEST_ASYNCIO:
                    nest_asyncio.apply(AsyncSupport._event_loop)
                    self.logger.info("Applied nest_asyncio to event loop")
                    
                self.logger.info("Initialized standard asyncio event loop")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize event loop: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            # Fall back to default asyncio event loop
            try:
                AsyncSupport._event_loop = asyncio.get_event_loop()
            except RuntimeError:
                AsyncSupport._event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(AsyncSupport._event_loop)
            
    @staticmethod
    def get_event_loop():
        """Get the current event loop or initialize one if needed."""
        if AsyncSupport._instance is None:
            AsyncSupport()
        if AsyncSupport._event_loop is not None:
            return AsyncSupport._event_loop
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            AsyncSupport._event_loop = loop
            return loop
    
    @staticmethod
    def run_coroutine(coro: Coroutine) -> Any:
        """Run a coroutine safely in the current event loop.
        
        Args:
            coro: The coroutine to run
            
        Returns:
            The result of the coroutine
        """
        if AsyncSupport._instance is None:
            AsyncSupport()
            
        loop = AsyncSupport.get_event_loop()
        if loop.is_running():
            # If loop is running, use asyncio.create_task to schedule
            task = asyncio.create_task(coro)
            return task
        else:
            # Otherwise run it immediately
            return loop.run_until_complete(coro)
    
    @staticmethod
    def schedule_coroutine(coro: Coroutine) -> asyncio.Task:
        """Schedule a coroutine to run in the event loop.
        
        Args:
            coro: The coroutine to schedule
            
        Returns:
            asyncio.Task: The created task
        """
        if AsyncSupport._instance is None:
            AsyncSupport()
            
        loop = AsyncSupport.get_event_loop()
        return asyncio.create_task(coro)
    
    @staticmethod
    def fire_and_forget(coro: Coroutine) -> None:
        """Schedule a coroutine to run without tracking its result.
        
        This method is useful for operations that don't need to be awaited or
        when you want to initiate an async operation from synchronous code.
        
        Args:
            coro: The coroutine to run
        """
        if AsyncSupport._instance is None:
            AsyncSupport()
            
        try:
            loop = AsyncSupport.get_event_loop()
            task = asyncio.create_task(coro)
            
            # Optional: add done callback to handle exceptions
            def _done_callback(task):
                try:
                    task.result()  # Retrieve result to prevent unhandled exceptions
                except Exception as e:
                    logger.error(f"Unhandled exception in fire_and_forget task: {e}")
                    
            task.add_done_callback(_done_callback)
        except Exception as e:
            logger.error(f"Error scheduling coroutine: {e}")
    
    @staticmethod
    def as_async_task(func):
        """Decorator to convert a function to an async task.
        
        This decorator can be used on both synchronous and asynchronous functions
        to ensure they are properly executed as tasks in the event loop.
        
        Args:
            func: The function to decorate
            
        Returns:
            A decorated function that returns an asyncio.Task
        """
        @wraps(func)
        async def _async_wrapper(*args, **kwargs):
            """Inner async wrapper function."""
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                # Run synchronous function in executor to prevent blocking
                loop = AsyncSupport.get_event_loop()
                return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
                
        @wraps(func)
        def _sync_wrapper(*args, **kwargs):
            """Outer synchronous wrapper function."""
            if AsyncSupport._instance is None:
                AsyncSupport()
                
            task = AsyncSupport.schedule_coroutine(_async_wrapper(*args, **kwargs))
            return task
            
        return _sync_wrapper


# Helper function to ensure a method is properly awaited
def ensure_awaited(coro_or_func: Union[Callable[..., T], Coroutine[Any, Any, T]]) -> Union[T, asyncio.Task[T]]:
    """Ensure a coroutine is properly awaited or a function is properly called.
    
    This helper function detects if we're in an async context and handles the
    operation accordingly. If the input is a coroutine, it will be properly awaited
    or scheduled as a task. If it's a function, it will be called directly.
    
    Args:
        coro_or_func: A coroutine or function
        
    Returns:
        The result of the coroutine/function or an asyncio.Task
    """
    if asyncio.iscoroutine(coro_or_func):
        try:
            # Check if we're in an async context
            asyncio.get_running_loop()
            # If this succeeds, we're in an async context and should return the coroutine for awaiting
            return coro_or_func
        except RuntimeError:
            # We're not in an async context, schedule with AsyncSupport
            return AsyncSupport.schedule_coroutine(coro_or_func)
    elif callable(coro_or_func):
        # It's a function, not a coroutine - just call it
        return coro_or_func()
    else:
        # Neither a coroutine nor a function - return as is
        return coro_or_func


# Initialize AsyncSupport when this module is imported
async_support = AsyncSupport()

# Export key functions at module level for convenience
get_event_loop = async_support.get_event_loop
run_coroutine = async_support.run_coroutine
schedule_coroutine = async_support.schedule_coroutine
fire_and_forget = async_support.fire_and_forget
as_async_task = async_support.as_async_task

__all__ = [
    'AsyncSupport', 'ensure_awaited', 'get_event_loop',
    'run_coroutine', 'schedule_coroutine', 'fire_and_forget', 
    'as_async_task', 'HAS_QASYNC', 'HAS_NEST_ASYNCIO'
]
