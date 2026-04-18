"""
SOTA 2026 Enhanced Logging - Organized, Non-Blocking, Location-Aware

Features:
- Rate limiting: Prevents log flooding from repeated messages
- Location tracking: Errors/warnings show exact file:line:function
- Async-safe: Non-blocking queue-based logging to prevent GUI freeze
- Deduplication: Collapses repeated messages with count
- Level filtering: Suppresses noise while keeping errors detailed
"""

import logging
import logging.handlers
import threading
import time
import traceback
import sys
import os
from collections import defaultdict
from typing import Optional, Dict, Any
from queue import Queue, Empty
from datetime import datetime


class RateLimitedFilter(logging.Filter):
    """Filter that rate-limits repeated messages to prevent log spam."""

    def __init__(self, rate_limit_seconds: float = 2.0, max_suppressed: int = 100):
        super().__init__()
        self._last_log_time: Dict[str, float] = {}
        self._suppressed_count: Dict[str, int] = defaultdict(int)
        self._rate_limit = rate_limit_seconds
        self._max_suppressed = max_suppressed
        self._lock = threading.Lock()

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.ERROR:
            return True
        key = f"{record.name}:{record.getMessage()[:100]}"
        current_time = time.time()
        with self._lock:
            last_time = self._last_log_time.get(key, 0)
            if current_time - last_time < self._rate_limit:
                self._suppressed_count[key] += 1
                if self._suppressed_count[key] >= self._max_suppressed:
                    record.msg = f"{record.msg} (×{self._suppressed_count[key]} repeated)"
                    self._suppressed_count[key] = 0
                    self._last_log_time[key] = current_time
                    return True
                return False
            if self._suppressed_count[key] > 0:
                record.msg = f"{record.msg} (×{self._suppressed_count[key]} suppressed)"
                self._suppressed_count[key] = 0
            self._last_log_time[key] = current_time
            return True


class LocationAwareFormatter(logging.Formatter):
    """Formatter that adds detailed location info for errors/warnings."""

    COLORS = {
        'DEBUG': '\033[90m',
        'INFO': '\033[37m',
        'WARNING': '\033[93m',
        'ERROR': '\033[91m',
        'CRITICAL': '\033[91;1m',
        'RESET': '\033[0m',
    }
    CATEGORY_COLORS = {
        'trading': '\033[32m',
        'mining': '\033[33m',
        'blockchain': '\033[35m',
        'wallet': '\033[34m',
        'thoth': '\033[91m',
        'redis': '\033[31m',
        'voice': '\033[92m',
        'gui': '\033[97m',
        'event': '\033[36m',
    }

    def __init__(self, use_colors: bool = True, show_location: bool = True):
        super().__init__()
        self.use_colors = use_colors
        self.show_location = show_location

    def _get_category_color(self, name: str) -> str:
        name_lower = name.lower()
        for cat, color in self.CATEGORY_COLORS.items():
            if cat in name_lower:
                return color
        return '\033[37m'

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        level_color = self.COLORS.get(record.levelname, '')
        cat_color = self._get_category_color(record.name)
        reset = self.COLORS['RESET'] if self.use_colors else ''
        if not self.use_colors:
            level_color = cat_color = ''
        name_parts = record.name.split('.')
        short_name = '.'.join(name_parts[-2:]) if len(name_parts) > 2 else record.name
        msg = record.getMessage()
        location = ""
        if self.show_location and record.levelno >= logging.WARNING:
            filename = os.path.basename(record.pathname)
            location = f" [{filename}:{record.lineno}:{record.funcName}]"
        if self.use_colors:
            formatted = (
                f"\033[90m{timestamp}\033[0m "
                f"{level_color}[{record.levelname[0]}]\033[0m "
                f"{cat_color}{short_name}\033[0m: "
                f"{msg}"
                f"\033[90m{location}\033[0m"
            )
        else:
            formatted = f"{timestamp} [{record.levelname[0]}] {short_name}: {msg}{location}"
        if record.exc_info and record.levelno >= logging.ERROR:
            formatted += f"\n{'─' * 60}\n"
            formatted += ''.join(traceback.format_exception(*record.exc_info))
            formatted += f"{'─' * 60}"
        return formatted


class AsyncSafeHandler(logging.Handler):
    """Non-blocking handler that queues log records for background processing."""

    def __init__(self, target_handler: logging.Handler, queue_size: int = 10000):
        super().__init__()
        self._queue: Queue = Queue(maxsize=queue_size)
        self._target = target_handler
        self._shutdown = False
        self._worker = threading.Thread(target=self._process_queue, daemon=True, name="LogWorker")
        self._worker.start()

    def emit(self, record: logging.LogRecord) -> None:
        if self._shutdown:
            return
        try:
            self._queue.put_nowait(record)
        except Exception:
            pass

    def _process_queue(self) -> None:
        while not self._shutdown:
            try:
                record = self._queue.get(timeout=0.5)
                self._target.emit(record)
            except Empty:
                continue
            except Exception:
                pass

    def close(self) -> None:
        self._shutdown = True
        if self._worker.is_alive():
            self._worker.join(timeout=2.0)
        super().close()


def install_enhanced_logging(level: int = logging.INFO) -> Optional[AsyncSafeHandler]:
    """Install enhanced logging: rate limiting, location, async-safe console."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(LocationAwareFormatter(use_colors=True, show_location=True))
    async_handler = AsyncSafeHandler(console_handler)
    async_handler.addFilter(RateLimitedFilter(rate_limit_seconds=2.0))
    root_logger.addHandler(async_handler)
    try:
        _log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
        os.makedirs(_log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(_log_dir, 'kingdom.log'), encoding='utf-8',
            maxBytes=10 * 1024 * 1024, backupCount=3
        )
        file_handler.setFormatter(LocationAwareFormatter(use_colors=False, show_location=True))
        root_logger.addHandler(file_handler)
    except Exception:
        pass
    return async_handler


def suppress_noisy_loggers() -> None:
    """Suppress known noisy loggers to reduce spam."""
    noisy_loggers = [
        'urllib3', 'requests', 'asyncio', 'aiohttp',
        'websockets', 'httpx', 'httpcore',
        'PIL', 'matplotlib', 'numba',
        'transformers', 'diffusers', 'torch',
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)
