#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOTA 2026 Resilience Patterns for Kingdom AI

Implements circuit breaker, retry with backoff, and smart fallbacks that
PRESERVE REAL OPERATIONS. Fallbacks are temporary - system continuously
attempts to restore real functionality.

Key Principles:
1. Fallbacks NEVER permanently replace real operations
2. Retry with exponential backoff before falling back
3. Circuit breaker prevents cascading failures
4. Background recovery attempts restore real operations
5. Cache successful responses for intelligent fallbacks
"""

import asyncio
import functools
import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Generic, List, cast
from collections import deque

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation - requests flow through
    OPEN = "open"          # Failure detected - requests blocked, fallback used
    HALF_OPEN = "half_open"  # Testing recovery - one request allowed


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Failures before opening circuit
    success_threshold: int = 2          # Successes needed to close circuit
    timeout_seconds: float = 30.0       # Time before trying half-open
    reset_timeout_seconds: float = 60.0 # Full reset timeout


@dataclass 
class RetryConfig:
    """Configuration for retry with backoff."""
    max_retries: int = 3
    base_delay: float = 1.0           # Initial delay in seconds
    max_delay: float = 30.0           # Maximum delay cap
    exponential_base: float = 2.0     # Exponential backoff multiplier
    jitter: bool = True               # Add randomness to prevent thundering herd


@dataclass
class OperationResult(Generic[T]):
    """Result of an operation with metadata."""
    success: bool
    value: Optional[T] = None
    error: Optional[Exception] = None
    from_fallback: bool = False
    from_cache: bool = False
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class SmartCache:
    """
    Cache for fallback values with TTL and staleness tracking.
    Stale values can still be used as fallback but trigger refresh.
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300.0):
        self._cache: Dict[str, tuple] = {}  # key -> (value, timestamp, stale)
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[tuple]:
        """Get cached value. Returns (value, is_stale) or None."""
        with self._lock:
            if key not in self._cache:
                return None
            value, timestamp, _ = self._cache[key]
            age = (datetime.now() - timestamp).total_seconds()
            is_stale = age > self._ttl
            return (value, is_stale)
    
    def set(self, key: str, value: Any) -> None:
        """Cache a value."""
        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self._max_size:
                oldest_key = min(self._cache.keys(), 
                               key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
            self._cache[key] = (value, datetime.now(), False)
    
    def mark_stale(self, key: str) -> None:
        """Mark a cached value as stale."""
        with self._lock:
            if key in self._cache:
                value, timestamp, _ = self._cache[key]
                self._cache[key] = (value, timestamp, True)


class CircuitBreaker:
    """
    SOTA 2026 Circuit Breaker that protects services while enabling recovery.
    
    Key feature: Even when circuit is OPEN, it periodically attempts real
    operations in the background to detect recovery.
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_state_change: datetime = datetime.now()
        self._lock = threading.RLock()
        self._recovery_task: Optional[asyncio.Task] = None
        
    @property
    def state(self) -> CircuitState:
        with self._lock:
            # Auto-transition from OPEN to HALF_OPEN after timeout
            if self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                    if elapsed >= self.config.timeout_seconds:
                        self._state = CircuitState.HALF_OPEN
                        self._last_state_change = datetime.now()
                        logger.info(f"🔄 Circuit '{self.name}' transitioning to HALF_OPEN")
            return self._state
    
    def record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._success_count = 0
                    self._last_state_change = datetime.now()
                    logger.info(f"✅ Circuit '{self.name}' CLOSED - service recovered")
            elif self._state == CircuitState.OPEN:
                # Success during OPEN means service recovered
                self._state = CircuitState.CLOSED
                self._success_count = 0
                self._last_state_change = datetime.now()
                logger.info(f"✅ Circuit '{self.name}' CLOSED - service recovered")
    
    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Record a failed operation."""
        with self._lock:
            self._failure_count += 1
            self._success_count = 0
            self._last_failure_time = datetime.now()
            
            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery test - go back to OPEN
                self._state = CircuitState.OPEN
                self._last_state_change = datetime.now()
                logger.warning(f"⚠️ Circuit '{self.name}' back to OPEN - recovery failed")
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._last_state_change = datetime.now()
                    logger.warning(f"🔴 Circuit '{self.name}' OPEN - too many failures: {error}")
    
    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        state = self.state  # Triggers auto-transition check
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.HALF_OPEN:
            return True  # Allow probe request
        else:  # OPEN
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
                "last_state_change": self._last_state_change.isoformat()
            }


class ResilientOperation:
    """
    SOTA 2026 Resilient Operation wrapper.
    
    Combines circuit breaker, retry with backoff, caching, and smart fallbacks
    that PRESERVE the ability to perform real operations.
    """
    
    def __init__(
        self,
        name: str,
        operation: Callable[..., T],
        fallback: Optional[Callable[..., T]] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        cache_key_fn: Optional[Callable[..., str]] = None,
        cache_ttl: float = 300.0
    ):
        self.name = name
        self._operation = operation
        self._fallback = fallback
        self._circuit = CircuitBreaker(name, circuit_config)
        self._retry_config = retry_config or RetryConfig()
        self._cache = SmartCache(ttl_seconds=cache_ttl)
        self._cache_key_fn = cache_key_fn
        self._recovery_thread: Optional[threading.Thread] = None
        self._stop_recovery = threading.Event()
        
    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key for operation arguments."""
        if self._cache_key_fn:
            return self._cache_key_fn(*args, **kwargs)
        return f"{self.name}:{hash(str(args) + str(sorted(kwargs.items())))}"
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt with exponential backoff."""
        import random
        delay = min(
            self._retry_config.base_delay * (self._retry_config.exponential_base ** attempt),
            self._retry_config.max_delay
        )
        if self._retry_config.jitter:
            delay *= (0.5 + random.random())  # Add 50-150% jitter
        return delay
    
    def execute(self, *args, **kwargs) -> OperationResult[Any]:
        """
        Execute operation with full resilience patterns.
        
        1. Check circuit breaker
        2. Try operation with retries
        3. Cache successful results
        4. Use fallback if needed (from cache or fallback function)
        5. Start background recovery if circuit opens
        """
        cache_key = self._get_cache_key(*args, **kwargs)
        
        # Check if circuit allows request
        if not self._circuit.allow_request():
            # Circuit is OPEN - use fallback but schedule recovery attempt
            self._start_background_recovery(args, kwargs)
            return self._get_fallback_result(cache_key, *args, **kwargs)
        
        # Try operation with retries
        last_error: Optional[Exception] = None
        for attempt in range(self._retry_config.max_retries + 1):
            try:
                result = self._operation(*args, **kwargs)
                self._circuit.record_success()
                
                # Cache successful result
                self._cache.set(cache_key, result)
                
                return OperationResult(
                    success=True,
                    value=result,
                    retry_count=attempt
                )
                
            except Exception as e:
                last_error = e
                logger.warning(f"Operation '{self.name}' attempt {attempt + 1} failed: {e}")
                
                if attempt < self._retry_config.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.info(f"Retrying '{self.name}' in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    self._circuit.record_failure(e)
        
        # All retries exhausted - use fallback
        return self._get_fallback_result(cache_key, *args, **kwargs, error=last_error)
    
    async def execute_async(self, *args, **kwargs) -> OperationResult[Any]:
        """Async version of execute."""
        cache_key = self._get_cache_key(*args, **kwargs)
        
        if not self._circuit.allow_request():
            self._start_background_recovery(args, kwargs)
            return self._get_fallback_result(cache_key, *args, **kwargs)
        
        last_error: Optional[Exception] = None
        for attempt in range(self._retry_config.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(self._operation):
                    result = await self._operation(*args, **kwargs)
                else:
                    result = self._operation(*args, **kwargs)
                    
                self._circuit.record_success()
                self._cache.set(cache_key, result)
                
                return OperationResult(
                    success=True,
                    value=result,
                    retry_count=attempt
                )
                
            except Exception as e:
                last_error = e
                logger.warning(f"Async operation '{self.name}' attempt {attempt + 1} failed: {e}")
                
                if attempt < self._retry_config.max_retries:
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)
                else:
                    self._circuit.record_failure(e)
        
        return self._get_fallback_result(cache_key, *args, **kwargs, error=last_error)
    
    def _get_fallback_result(
        self, 
        cache_key: str, 
        *args, 
        error: Optional[Exception] = None,
        **kwargs
    ) -> OperationResult[Any]:
        """Get fallback result from cache or fallback function."""
        # Try cache first
        cached = self._cache.get(cache_key)
        if cached:
            value, is_stale = cached
            if is_stale:
                logger.info(f"Using stale cached value for '{self.name}'")
            return OperationResult(
                success=True,
                value=value,
                from_fallback=True,
                from_cache=True,
                error=error
            )
        
        # Try fallback function
        if self._fallback:
            try:
                fallback_value = self._fallback(*args, **kwargs)
                return OperationResult(
                    success=True,
                    value=fallback_value,
                    from_fallback=True,
                    error=error
                )
            except Exception as fb_error:
                logger.error(f"Fallback for '{self.name}' also failed: {fb_error}")
        
        # Complete failure
        return OperationResult(
            success=False,
            error=error or Exception(f"Operation '{self.name}' failed with no fallback")
        )
    
    def _start_background_recovery(self, args: tuple, kwargs: dict) -> None:
        """Start background thread to periodically attempt real operation."""
        if self._recovery_thread and self._recovery_thread.is_alive():
            return  # Already running
        
        def recovery_loop():
            while not self._stop_recovery.is_set():
                # Wait for recovery timeout
                self._stop_recovery.wait(self._circuit.config.timeout_seconds)
                if self._stop_recovery.is_set():
                    break
                
                # Attempt real operation
                try:
                    result = self._operation(*args, **kwargs)
                    self._circuit.record_success()
                    cache_key = self._get_cache_key(*args, **kwargs)
                    self._cache.set(cache_key, result)
                    logger.info(f"✅ Background recovery for '{self.name}' succeeded!")
                    break
                except Exception as e:
                    self._circuit.record_failure(e)
                    logger.debug(f"Background recovery for '{self.name}' failed: {e}")
        
        self._stop_recovery.clear()
        self._recovery_thread = threading.Thread(
            target=recovery_loop,
            name=f"recovery_{self.name}",
            daemon=True
        )
        self._recovery_thread.start()
    
    def stop(self) -> None:
        """Stop background recovery."""
        self._stop_recovery.set()
        if self._recovery_thread:
            self._recovery_thread.join(timeout=1.0)
    
    def get_status(self) -> Dict[str, Any]:
        """Get operation status."""
        return {
            "name": self.name,
            "circuit": self._circuit.get_status(),
            "cache_size": len(self._cache._cache),
            "recovery_active": self._recovery_thread.is_alive() if self._recovery_thread else False
        }


def resilient(
    name: str = None,
    fallback: Callable = None,
    max_retries: int = 3,
    circuit_failure_threshold: int = 5,
    cache_ttl: float = 300.0
):
    """
    Decorator to make any function resilient with SOTA 2026 patterns.
    
    Usage:
        @resilient(name="fetch_prices", max_retries=3)
        def fetch_exchange_prices(symbol):
            return exchange.fetch_ticker(symbol)
    """
    class ResilientWrapper:
        """Callable wrapper class for resilient operations."""
        
        def __init__(self, func: Callable[..., T], resilient_op: ResilientOperation):
            self._func = func
            self.resilient_op = resilient_op
            self.__name__ = func.__name__
            self.__doc__ = func.__doc__
            functools.update_wrapper(self, func)
        
        def __call__(self, *args, **kwargs) -> OperationResult[Any]:
            if asyncio.iscoroutinefunction(self._func):
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    self.resilient_op.execute_async(*args, **kwargs)
                )
            return self.resilient_op.execute(*args, **kwargs)
        
        def get_status(self) -> Dict[str, Any]:
            """Get resilient operation status."""
            return self.resilient_op.get_status()
    
    def decorator(func: Callable[..., T]) -> ResilientWrapper:
        op_name = name or func.__name__
        
        resilient_op = ResilientOperation(
            name=op_name,
            operation=func,
            fallback=fallback,
            circuit_config=CircuitBreakerConfig(failure_threshold=circuit_failure_threshold),
            retry_config=RetryConfig(max_retries=max_retries),
            cache_ttl=cache_ttl
        )
        
        return ResilientWrapper(func, resilient_op)
    
    return decorator


# Global registry for all resilient operations
_resilient_operations: Dict[str, ResilientOperation] = {}


def register_resilient_operation(name: str, op: ResilientOperation) -> None:
    """Register a resilient operation globally."""
    _resilient_operations[name] = op


def get_resilience_status() -> Dict[str, Any]:
    """Get status of all registered resilient operations."""
    return {
        name: op.get_status() 
        for name, op in _resilient_operations.items()
    }


def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get a circuit breaker by name."""
    op = _resilient_operations.get(name)
    return op._circuit if op else None


# Pre-configured resilient operations for Kingdom AI systems
class KingdomResilience:
    """
    Pre-configured resilience patterns for Kingdom AI systems.
    Each operation preserves real functionality while handling failures gracefully.
    """
    
    @staticmethod
    def create_exchange_operation(
        exchange_name: str,
        operation: Callable,
        fallback: Optional[Callable] = None
    ) -> ResilientOperation:
        """Create resilient operation for exchange API calls."""
        op = ResilientOperation(
            name=f"exchange_{exchange_name}",
            operation=operation,
            fallback=fallback,
            circuit_config=CircuitBreakerConfig(
                failure_threshold=3,      # Exchanges fail fast
                timeout_seconds=10.0,     # Quick recovery check
                success_threshold=1       # One success to recover
            ),
            retry_config=RetryConfig(
                max_retries=2,            # Limited retries for rate limits
                base_delay=0.5,
                max_delay=5.0
            ),
            cache_ttl=30.0               # 30s cache for market data
        )
        register_resilient_operation(f"exchange_{exchange_name}", op)
        return op
    
    @staticmethod
    def create_blockchain_operation(
        network: str,
        operation: Callable,
        fallback: Optional[Callable] = None
    ) -> ResilientOperation:
        """Create resilient operation for blockchain RPC calls."""
        op = ResilientOperation(
            name=f"blockchain_{network}",
            operation=operation,
            fallback=fallback,
            circuit_config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
                success_threshold=2
            ),
            retry_config=RetryConfig(
                max_retries=3,
                base_delay=1.0,
                max_delay=10.0
            ),
            cache_ttl=60.0              # 1 minute cache for blockchain data
        )
        register_resilient_operation(f"blockchain_{network}", op)
        return op
    
    @staticmethod
    def create_ai_operation(
        model_name: str,
        operation: Callable,
        fallback: Optional[Callable] = None
    ) -> ResilientOperation:
        """Create resilient operation for AI/Ollama calls."""
        op = ResilientOperation(
            name=f"ai_{model_name}",
            operation=operation,
            fallback=fallback,
            circuit_config=CircuitBreakerConfig(
                failure_threshold=3,
                timeout_seconds=60.0,    # AI models may need time to load
                success_threshold=1
            ),
            retry_config=RetryConfig(
                max_retries=2,
                base_delay=2.0,          # AI inference can be slow
                max_delay=30.0
            ),
            cache_ttl=3600.0            # 1 hour cache for AI responses
        )
        register_resilient_operation(f"ai_{model_name}", op)
        return op
    
    @staticmethod
    def create_mining_operation(
        pool_name: str,
        operation: Callable,
        fallback: Optional[Callable] = None
    ) -> ResilientOperation:
        """Create resilient operation for mining pool operations."""
        op = ResilientOperation(
            name=f"mining_{pool_name}",
            operation=operation,
            fallback=fallback,
            circuit_config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
                success_threshold=2
            ),
            retry_config=RetryConfig(
                max_retries=3,
                base_delay=1.0,
                max_delay=15.0
            ),
            cache_ttl=120.0             # 2 minute cache for mining stats
        )
        register_resilient_operation(f"mining_{pool_name}", op)
        return op


logger.info("✅ SOTA 2026 Resilience Patterns module loaded")
