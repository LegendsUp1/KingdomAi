"""
SOTA 2025 HIGH-FREQUENCY TRADING COMMUNICATION SYSTEM
=====================================================

This module provides the core infrastructure for millisecond-level
communication across the entire Kingdom AI system.

PERFORMANCE SPECIFICATIONS:
- Data fetch: 100ms interval (10 updates/second)
- UI updates: 250ms interval (4 updates/second)
- Event propagation: <10ms latency
- Thread pool: 8-16 dedicated worker threads
- Buffer: O(1) circular deque operations
- Zero-copy data passing where possible

ARCHITECTURE:
┌─────────────────────────────────────────────────────────────────┐
│                    HFT COMMUNICATION LAYER                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ HFTEventBus  │◄──►│ HFTDataPool  │◄──►│ HFTWorkerPool│      │
│  │ (pub/sub)    │    │ (buffers)    │    │ (threads)    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│          │                  │                   │               │
│          ▼                  ▼                   ▼               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              COMPONENT CONNECTORS                        │   │
│  │  Trading │ Mining │ Wallet │ Thoth AI │ Dashboard       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

Author: Kingdom AI Team
Version: 2.0.0 (SOTA 2025)
"""

import asyncio
import json
import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from queue import Queue, Empty
import weakref

# PyQt6 imports for Qt integration
try:
    from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QRunnable, QThreadPool, pyqtSlot, QMetaObject, Qt, Q_ARG
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    QObject = object
    pyqtSignal = lambda *args: None

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class HFTEventPriority(Enum):
    """Event priority levels for HFT system."""
    CRITICAL = 0    # Price updates, order execution - process immediately
    HIGH = 1        # Risk alerts, position changes - process within 50ms
    NORMAL = 2      # Analytics, sentiment - process within 250ms
    LOW = 3         # Logging, metrics - process within 1000ms


@dataclass
class HFTEvent:
    """High-frequency trading event with metadata."""
    event_type: str
    data: Any
    priority: HFTEventPriority = HFTEventPriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"
    
    def age_ms(self) -> float:
        """Get event age in milliseconds."""
        return (time.time() - self.timestamp) * 1000


@dataclass
class HFTMetrics:
    """Performance metrics for HFT system."""
    events_processed: int = 0
    events_dropped: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    throughput_per_sec: float = 0.0
    buffer_utilization: float = 0.0
    active_workers: int = 0


# =============================================================================
# HFT DATA BUFFER - O(1) CIRCULAR BUFFER
# =============================================================================

class HFTDataBuffer:
    """
    High-performance circular buffer for HFT data.
    Thread-safe with minimal locking overhead.
    
    Features:
    - O(1) append and pop operations
    - Thread-safe with RLock
    - Automatic overflow handling
    - Latest value tracking per key
    """
    
    __slots__ = ('_buffer', '_latest', '_lock', '_maxlen', '_overflow_count')
    
    def __init__(self, maxlen: int = 10000, max_size: int = None):
        # Support both maxlen and max_size for compatibility
        size = max_size if max_size is not None else maxlen
        self._buffer: deque = deque(maxlen=size)
        self._latest: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._maxlen = size
        self._overflow_count = 0
    
    def push(self, value: Any, key: str = 'default') -> None:
        """Alias for put() - adds data to buffer."""
        self.put(key, value)
    
    def put(self, key: str, value: Any, timestamp: float = None) -> None:
        """Add data to buffer (thread-safe, O(1))."""
        if timestamp is None:
            timestamp = time.time()
        
        entry = {
            'key': key,
            'value': value,
            'timestamp': timestamp
        }
        
        with self._lock:
            if len(self._buffer) >= self._maxlen:
                self._overflow_count += 1
            self._buffer.append(entry)
            self._latest[key] = entry
    
    def get_latest(self, key: str = None) -> Optional[Any]:
        """Get latest value for key or all latest values."""
        with self._lock:
            if key:
                entry = self._latest.get(key)
                return entry['value'] if entry else None
            return {k: v['value'] for k, v in self._latest.items()}
    
    def get_history(self, key: str = None, limit: int = 100) -> List[Any]:
        """Get historical values (thread-safe)."""
        with self._lock:
            if key:
                return [e['value'] for e in list(self._buffer)[-limit:] if e['key'] == key]
            return [e['value'] for e in list(self._buffer)[-limit:]]
    
    def clear(self) -> None:
        """Clear all data."""
        with self._lock:
            self._buffer.clear()
            self._latest.clear()
    
    @property
    def size(self) -> int:
        """Current buffer size."""
        return len(self._buffer)
    
    @property
    def utilization(self) -> float:
        """Buffer utilization percentage."""
        return len(self._buffer) / self._maxlen if self._maxlen > 0 else 0.0


# =============================================================================
# HFT WORKER - THREAD POOL WORKER
# =============================================================================

class HFTWorker:
    """
    High-frequency trading worker for thread pool execution.
    Executes tasks without blocking the main thread.
    """
    
    def __init__(self, func: Callable, callback: Callable = None, *args, **kwargs):
        self.func = func
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.error = None
        self.start_time = None
        self.end_time = None
        self._auto_delete = True
    
    def setAutoDelete(self, auto: bool):
        """Qt compatibility method."""
        self._auto_delete = auto
    
    def run(self):
        """Execute the worker task."""
        self.start_time = time.time()
        try:
            self.result = self.func(*self.args, **self.kwargs)
            if self.callback:
                self.callback(self.result)
        except Exception as e:
            self.error = e
            logger.error(f"HFT Worker error: {e}")
        finally:
            self.end_time = time.time()
    
    @property
    def execution_time_ms(self) -> float:
        """Get execution time in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0


# =============================================================================
# HFT EVENT BUS - HIGH-FREQUENCY PUB/SUB
# =============================================================================

class HFTEventBus:
    """
    High-frequency event bus with priority queuing.
    
    Features:
    - Priority-based event processing
    - Non-blocking publish
    - Batch event handling
    - Latency tracking
    """
    
    # Singleton instance
    _instance: Optional['HFTEventBus'] = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> 'HFTEventBus':
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = HFTEventBus()
        return cls._instance
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._priority_queues: Dict[HFTEventPriority, deque] = {
            p: deque(maxlen=10000) for p in HFTEventPriority
        }
        self._lock = threading.RLock()
        self._metrics = HFTMetrics()
        self._latency_samples: deque = deque(maxlen=1000)
        self._running = False
        self._processor_thread: Optional[threading.Thread] = None
        
        logger.info("🚀 HFT EventBus initialized")
    
    def subscribe(self, event_type: str, handler: Callable, 
                  priority: HFTEventPriority = HFTEventPriority.NORMAL) -> bool:
        """Subscribe to an event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.debug(f"HFT: Subscribed {handler.__name__} to {event_type}")
                return True
            return False
    
    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """Unsubscribe from an event type."""
        with self._lock:
            if event_type in self._subscribers:
                if handler in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(handler)
                    return True
            return False
    
    def publish(self, event_type: str, data: Any = None,
                priority: HFTEventPriority = HFTEventPriority.NORMAL,
                source: str = "unknown") -> bool:
        """
        Publish an event (non-blocking).
        Events are queued by priority and processed asynchronously.
        """
        event = HFTEvent(
            event_type=event_type,
            data=data,
            priority=priority,
            source=source
        )
        
        # Add to priority queue (non-blocking)
        self._priority_queues[priority].append(event)
        return True
    
    def publish_immediate(self, event_type: str, data: Any = None) -> bool:
        """
        Publish and process event immediately (blocking).
        Use for critical events that must be processed synchronously.
        """
        start_time = time.time()
        
        with self._lock:
            handlers = self._subscribers.get(event_type, [])
        
        success = True
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    # Handle async handlers
                    try:
                        loop = asyncio.get_running_loop()
                        asyncio.create_task(handler(data))
                    except RuntimeError:
                        # No event loop, skip
                        pass
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"HFT handler error: {e}")
                success = False
        
        # Track latency
        latency = (time.time() - start_time) * 1000
        self._latency_samples.append(latency)
        self._metrics.events_processed += 1
        
        return success
    
    def start_processor(self, interval_ms: int = 10) -> None:
        """Start the background event processor."""
        if self._running:
            return
        
        self._running = True
        
        def processor_loop():
            while self._running:
                try:
                    # Process events by priority
                    for priority in HFTEventPriority:
                        queue = self._priority_queues[priority]
                        
                        # Process up to 100 events per priority per cycle
                        processed = 0
                        while queue and processed < 100:
                            try:
                                event = queue.popleft()
                                self._process_event(event)
                                processed += 1
                            except IndexError:
                                break
                    
                    # Sleep for interval
                    time.sleep(interval_ms / 1000)
                    
                except Exception as e:
                    logger.error(f"HFT processor error: {e}")
        
        self._processor_thread = threading.Thread(
            target=processor_loop,
            daemon=True,
            name="HFT-EventProcessor"
        )
        self._processor_thread.start()
        logger.info(f"🚀 HFT Event processor started ({interval_ms}ms interval)")
    
    def stop_processor(self) -> None:
        """Stop the background event processor."""
        self._running = False
        if self._processor_thread:
            self._processor_thread.join(timeout=1.0)
        logger.info("🛑 HFT Event processor stopped")
    
    def _process_event(self, event: HFTEvent) -> None:
        """Process a single event."""
        start_time = time.time()
        
        with self._lock:
            handlers = self._subscribers.get(event.event_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    try:
                        loop = asyncio.get_running_loop()
                        asyncio.create_task(handler(event.data))
                    except RuntimeError:
                        pass
                else:
                    handler(event.data)
            except Exception as e:
                logger.error(f"HFT handler error for {event.event_type}: {e}")
        
        # Update metrics
        latency = (time.time() - start_time) * 1000
        self._latency_samples.append(latency)
        self._metrics.events_processed += 1
        self._update_metrics(latency)
    
    def _update_metrics(self, latency_ms: float) -> None:
        """Update performance metrics."""
        self._metrics.avg_latency_ms = (
            sum(self._latency_samples) / len(self._latency_samples)
            if self._latency_samples else 0.0
        )
        self._metrics.max_latency_ms = max(
            self._metrics.max_latency_ms, latency_ms
        )
        self._metrics.min_latency_ms = min(
            self._metrics.min_latency_ms, latency_ms
        )
    
    def get_metrics(self) -> HFTMetrics:
        """Get current performance metrics."""
        return self._metrics


# =============================================================================
# HFT COMMUNICATION MANAGER - CENTRAL COORDINATOR
# =============================================================================

class HFTCommunicationManager:
    """
    Central coordinator for all HFT communication.
    
    Manages:
    - Thread pool for worker execution
    - Data buffers for each component
    - Event routing and prioritization
    - Performance monitoring
    """
    
    # Singleton instance
    _instance: Optional['HFTCommunicationManager'] = None
    _lock = threading.Lock()
    
    # Timing constants (milliseconds)
    DATA_FETCH_INTERVAL_MS = 100      # 10 updates/second
    UI_UPDATE_INTERVAL_MS = 250       # 4 updates/second
    ANALYTICS_INTERVAL_MS = 500       # 2 updates/second
    BACKGROUND_INTERVAL_MS = 1000     # 1 update/second
    
    @classmethod
    def get_instance(cls) -> 'HFTCommunicationManager':
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = HFTCommunicationManager()
        return cls._instance
    
    def __init__(self):
        # Thread pool for worker execution
        if HAS_PYQT:
            self._thread_pool = QThreadPool.globalInstance()
            self._thread_pool.setMaxThreadCount(16)
        else:
            # Lazy init to prevent segfault
            self._thread_pool = None
            self._max_workers = 16
        
        # Data buffers for different components
        self._buffers: Dict[str, HFTDataBuffer] = {
            'prices': HFTDataBuffer(maxlen=50000),      # Price data
            'orderbook': HFTDataBuffer(maxlen=10000),   # Order book
            'trades': HFTDataBuffer(maxlen=20000),      # Recent trades
            'sentiment': HFTDataBuffer(maxlen=5000),    # Sentiment data
            'risk': HFTDataBuffer(maxlen=5000),         # Risk metrics
            'analytics': HFTDataBuffer(maxlen=10000),   # Analytics data
            'mining': HFTDataBuffer(maxlen=5000),       # Mining data
            'wallet': HFTDataBuffer(maxlen=5000),       # Wallet data
        }
        
        # Event bus for pub/sub
        self._event_bus = HFTEventBus.get_instance()
        
        # Component connectors
        self._connectors: Dict[str, Any] = {}
        
        # Timers for periodic updates
        self._timers: Dict[str, Any] = {}
        
        # Running state
        self._running = False
        
        # Metrics
        self._start_time = time.time()
        self._total_operations = 0
        
        logger.info(f"🚀 HFT Communication Manager initialized - {self._get_thread_count()} threads")
    
    def _get_thread_count(self) -> int:
        """Get current thread pool size."""
        if HAS_PYQT and hasattr(self._thread_pool, 'maxThreadCount'):
            return self._thread_pool.maxThreadCount()
        elif hasattr(self._thread_pool, '_max_workers'):
            return self._thread_pool._max_workers
        return 16  # Default
    
    def start(self) -> None:
        """Start the HFT communication system."""
        if self._running:
            return
        
        self._running = True
        
        # Start event processor
        self._event_bus.start_processor(interval_ms=10)
        
        logger.info("🚀 HFT Communication System ACTIVE")
        logger.info(f"   Data fetch: {self.DATA_FETCH_INTERVAL_MS}ms")
        logger.info(f"   UI update: {self.UI_UPDATE_INTERVAL_MS}ms")
        logger.info(f"   Analytics: {self.ANALYTICS_INTERVAL_MS}ms")
        logger.info(f"   Background: {self.BACKGROUND_INTERVAL_MS}ms")
    
    def stop(self) -> None:
        """Stop the HFT communication system."""
        self._running = False
        
        # Stop event processor
        self._event_bus.stop_processor()
        
        # Stop all timers
        for timer in self._timers.values():
            if HAS_PYQT and hasattr(timer, 'stop'):
                timer.stop()
        
        logger.info("🛑 HFT Communication System stopped")
    
    def submit_task(self, func: Callable, callback: Callable = None,
                    *args, **kwargs) -> None:
        """
        Submit a task to the thread pool (non-blocking).
        
        Args:
            func: Function to execute
            callback: Optional callback for result
            *args, **kwargs: Arguments for func
        """
        if HAS_PYQT and hasattr(self._thread_pool, 'start'):
            # PyQt QThreadPool
            worker = HFTWorker(func, callback, *args, **kwargs)
            # Wrap in QRunnable for Qt
            class QtWorker(QRunnable):
                def __init__(self, hft_worker):
                    super().__init__()
                    self.hft_worker = hft_worker
                    self.setAutoDelete(True)
                
                def run(self):
                    self.hft_worker.run()
            
            qt_worker = QtWorker(worker)
            self._thread_pool.start(qt_worker)
        else:
            # Standard ThreadPoolExecutor
            def task_wrapper():
                worker = HFTWorker(func, callback, *args, **kwargs)
                worker.run()
                return worker.result
            
            self._thread_pool.submit(task_wrapper)
        
        self._total_operations += 1
    
    def get_buffer(self, name: str) -> Optional[HFTDataBuffer]:
        """Get a data buffer by name."""
        return self._buffers.get(name)
    
    def put_data(self, buffer_name: str, key: str, value: Any) -> bool:
        """Put data into a buffer."""
        buffer = self._buffers.get(buffer_name)
        if buffer:
            buffer.put(key, value)
            return True
        return False
    
    def get_data(self, buffer_name: str, key: str = None) -> Any:
        """Get data from a buffer."""
        buffer = self._buffers.get(buffer_name)
        if buffer:
            return buffer.get_latest(key)
        return None
    
    def publish_event(self, event_type: str, data: Any = None,
                      priority: HFTEventPriority = HFTEventPriority.NORMAL) -> bool:
        """Publish an event through the HFT event bus."""
        return self._event_bus.publish(event_type, data, priority)
    
    def subscribe_event(self, event_type: str, handler: Callable) -> bool:
        """Subscribe to an event type."""
        return self._event_bus.subscribe(event_type, handler)
    
    def register_connector(self, name: str, connector: Any) -> None:
        """Register a component connector."""
        self._connectors[name] = connector
        logger.info(f"📡 Registered HFT connector: {name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive HFT system statistics."""
        uptime = time.time() - self._start_time
        event_metrics = self._event_bus.get_metrics()
        
        buffer_stats = {}
        for name, buffer in self._buffers.items():
            buffer_stats[name] = {
                'size': buffer.size,
                'utilization': f"{buffer.utilization * 100:.1f}%"
            }
        
        return {
            'uptime_seconds': uptime,
            'total_operations': self._total_operations,
            'operations_per_second': self._total_operations / uptime if uptime > 0 else 0,
            'thread_count': self._get_thread_count(),
            'active_connectors': len(self._connectors),
            'event_metrics': {
                'processed': event_metrics.events_processed,
                'avg_latency_ms': f"{event_metrics.avg_latency_ms:.2f}",
                'max_latency_ms': f"{event_metrics.max_latency_ms:.2f}",
            },
            'buffers': buffer_stats,
            'timing': {
                'data_fetch_ms': self.DATA_FETCH_INTERVAL_MS,
                'ui_update_ms': self.UI_UPDATE_INTERVAL_MS,
                'analytics_ms': self.ANALYTICS_INTERVAL_MS,
            }
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_hft_manager() -> HFTCommunicationManager:
    """Get the global HFT Communication Manager instance."""
    return HFTCommunicationManager.get_instance()


def get_hft_event_bus() -> HFTEventBus:
    """Get the global HFT Event Bus instance."""
    return HFTEventBus.get_instance()


def hft_publish(event_type: str, data: Any = None,
                priority: HFTEventPriority = HFTEventPriority.NORMAL) -> bool:
    """Convenience function to publish HFT events."""
    return get_hft_event_bus().publish(event_type, data, priority)


def hft_subscribe(event_type: str, handler: Callable) -> bool:
    """Convenience function to subscribe to HFT events."""
    return get_hft_event_bus().subscribe(event_type, handler)


def hft_submit_task(func: Callable, callback: Callable = None,
                    *args, **kwargs) -> None:
    """Convenience function to submit tasks to HFT thread pool."""
    get_hft_manager().submit_task(func, callback, *args, **kwargs)


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

# Auto-start HFT system when module is imported
_hft_manager: Optional[HFTCommunicationManager] = None

def init_hft_system() -> HFTCommunicationManager:
    """Initialize and start the HFT communication system."""
    global _hft_manager
    if _hft_manager is None:
        _hft_manager = get_hft_manager()
        _hft_manager.start()
    return _hft_manager


# Export all public classes and functions
__all__ = [
    'HFTEventPriority',
    'HFTEvent',
    'HFTMetrics',
    'HFTDataBuffer',
    'HFTWorker',
    'HFTEventBus',
    'HFTCommunicationManager',
    'get_hft_manager',
    'get_hft_event_bus',
    'hft_publish',
    'hft_subscribe',
    'hft_submit_task',
    'init_hft_system',
]
