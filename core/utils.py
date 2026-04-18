#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Core Utilities Module
Provides common utility functions and classes for various components.
"""

import os
import json
import time
import uuid
import logging
import hashlib
import threading
import asyncio
from typing import Any, Dict, Union, Callable, TypeVar

# Constants
DEFAULT_CONFIG_PATH = "config"
DEFAULT_LOG_PATH = "logs"
DEFAULT_TIMEOUT = 30  # seconds

# Type variables for generics
T = TypeVar('T')


class ThreadSafeDict(Dict[str, T]):
    """Thread-safe dictionary implementation."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()
    
    def __getitem__(self, key):
        with self._lock:
            return super().__getitem__(key)
    
    def __setitem__(self, key, value):
        with self._lock:
            super().__setitem__(key, value)
    
    def __delitem__(self, key):
        with self._lock:
            super().__delitem__(key)
    
    def get(self, key, default=None):
        with self._lock:
            return super().get(key, default)
    
    def pop(self, key, default=None):
        with self._lock:
            return super().pop(key, default)
    
    def update(self, *args, **kwargs):
        with self._lock:
            super().update(*args, **kwargs)


class AsyncUtils:
    """Async utilities for Kingdom AI."""
    
    @staticmethod
    async def gather_with_timeout(tasks, timeout=DEFAULT_TIMEOUT):
        """
        Run multiple tasks with a timeout.
        
        Args:
            tasks: List of tasks to run
            timeout: Timeout in seconds
            
        Returns:
            List of task results or None on timeout
        """
        try:
            return await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout)
        except asyncio.TimeoutError:
            logging.warning(f"Async tasks timed out after {timeout} seconds")
            return None
    
    @staticmethod
    def create_task(coroutine, name=None):
        """
        Create a named task with proper error handling.
        
        Args:
            coroutine: Coroutine to run
            name: Optional name for the task
            
        Returns:
            The created task
        """
        task = asyncio.create_task(coroutine)
        if name:
            # Set name if supported by Python version
            if hasattr(task, "set_name"):
                task.set_name(name)
        return task


class CryptoUtils:
    """Cryptographic utilities for Kingdom AI."""
    
    @staticmethod
    def sha256(data: Union[str, bytes]) -> str:
        """
        Compute SHA-256 hash of data.
        
        Args:
            data: Input data (string or bytes)
            
        Returns:
            Hexadecimal string of the hash
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def generate_uuid() -> str:
        """
        Generate a UUID (version 4).
        
        Returns:
            UUID as string
        """
        return str(uuid.uuid4())


class FileUtils:
    """File-related utilities for Kingdom AI."""
    
    @staticmethod
    def ensure_directory(path: str) -> bool:
        """
        Ensure a directory exists, creating it if necessary.
        
        Args:
            path: Directory path
            
        Returns:
            True if directory exists or was created, False otherwise
        """
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            logging.error(f"Error creating directory {path}: {str(e)}")
            return False
    
    @staticmethod
    def load_json(file_path: str, default: Any = None) -> Any:
        """
        Load JSON from a file.
        
        Args:
            file_path: Path to JSON file
            default: Default value if file doesn't exist or is invalid
            
        Returns:
            Loaded data or default
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading JSON from {file_path}: {str(e)}")
            return default
    
    @staticmethod
    def save_json(file_path: str, data: Any) -> bool:
        """
        Save data as JSON to a file.
        
        Args:
            file_path: Path to save JSON file
            data: Data to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
                
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logging.error(f"Error saving JSON to {file_path}: {str(e)}")
            return False


class Timer:
    """Simple timer utility for performance measurement."""
    
    def __init__(self, name: str = "Timer"):
        """
        Initialize a timer.
        
        Args:
            name: Timer name for logging
        """
        self.name = name
        self.start_time = None
        self.stop_time = None
    
    def __enter__(self):
        """Start the timer when entering a context."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the timer when exiting a context."""
        self.stop()
        
    def start(self):
        """Start the timer."""
        self.start_time = time.time()
        return self
    
    def stop(self):
        """Stop the timer."""
        self.stop_time = time.time()
        return self
    
    def elapsed(self) -> float:
        """
        Get elapsed time.
        
        Returns:
            Elapsed time in seconds
        """
        if self.start_time is None:
            return 0
        
        end_time = self.stop_time if self.stop_time is not None else time.time()
        return end_time - self.start_time
    
    def log_elapsed(self, level=logging.INFO):
        """
        Log elapsed time.
        
        Args:
            level: Logging level
        """
        elapsed = self.elapsed()
        logging.log(level, f"{self.name}: {elapsed:.4f} seconds")
        return elapsed


class Singleton:
    """
    Singleton metaclass for Kingdom AI.
    Usage: class MyClass(metaclass=Singleton):
    """
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class EventHandler:
    """Simple event handler for non-event-bus scenarios."""
    
    def __init__(self):
        """Initialize the event handler."""
        self.handlers = {}
        self._lock = threading.RLock()
    
    def add_handler(self, event_type: str, handler: Callable) -> None:
        """
        Add a handler for an event type.
        
        Args:
            event_type: Type of event
            handler: Handler function
        """
        with self._lock:
            if event_type not in self.handlers:
                self.handlers[event_type] = []
            
            if handler not in self.handlers[event_type]:
                self.handlers[event_type].append(handler)
    
    def remove_handler(self, event_type: str, handler: Callable) -> None:
        """
        Remove a handler for an event type.
        
        Args:
            event_type: Type of event
            handler: Handler function
        """
        with self._lock:
            if event_type in self.handlers and handler in self.handlers[event_type]:
                self.handlers[event_type].remove(handler)
                
                if not self.handlers[event_type]:
                    del self.handlers[event_type]
    
    def trigger(self, event_type: str, *args, **kwargs) -> None:
        """
        Trigger an event.
        
        Args:
            event_type: Type of event
            *args: Arguments to pass to handlers
            **kwargs: Keyword arguments to pass to handlers
        """
        with self._lock:
            if event_type in self.handlers:
                for handler in self.handlers[event_type]:
                    try:
                        handler(*args, **kwargs)
                    except Exception as e:
                        logging.error(f"Error in event handler for {event_type}: {str(e)}")


def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    Retry decorator for functions that may fail.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff: Backoff multiplier
        exceptions: Exceptions to catch
        
    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            mtries, mdelay = max_attempts, delay
            while mtries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    mtries -= 1
                    if mtries == 0:
                        raise
                    
                    logging.warning(f"Retry: {func.__name__} failed, retrying in {mdelay}s... ({max_attempts - mtries}/{max_attempts})")
                    time.sleep(mdelay)
                    mdelay *= backoff
            return func(*args, **kwargs)
        return wrapper
    return decorator


def memoize(func):
    """
    Memoization decorator for caching function results.
    
    Args:
        func: Function to memoize
        
    Returns:
        Decorated function
    """
    cache = {}
    
    def wrapper(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def get_config_path(filename: str) -> str:
    """
    Get the full path to a config file.
    
    Args:
        filename: Config filename
        
    Returns:
        Full path to config file
    """
    return os.path.join(DEFAULT_CONFIG_PATH, filename)


def get_log_path(filename: str) -> str:
    """
    Get the full path to a log file.
    
    Args:
        filename: Log filename
        
    Returns:
        Full path to log file
    """
    return os.path.join(DEFAULT_LOG_PATH, filename)


def parse_bool(value: Any) -> bool:
    """
    Parse a boolean value from various input types.
    
    Args:
        value: Input value (string, int, bool)
        
    Returns:
        Boolean representation of the value
    """
    if isinstance(value, bool):
        return value
    
    if isinstance(value, int):
        return value != 0
    
    if isinstance(value, str):
        value = value.lower()
        if value in ('true', 'yes', 'y', '1'):
            return True
        if value in ('false', 'no', 'n', '0'):
            return False
    
    return bool(value)


def safe_execute(func, *args, default=None, **kwargs):
    """
    Safely execute a function, returning default on error.
    
    Args:
        func: Function to execute
        *args: Arguments to pass to function
        default: Default value on error
        **kwargs: Keyword arguments to pass to function
        
    Returns:
        Function result or default on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logging.error(f"Error executing {func.__name__}: {str(e)}")
        return default
