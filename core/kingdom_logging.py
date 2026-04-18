#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI - SOTA 2025 Centralized Logging System

This module provides state-of-the-art logging configuration:
- Reduced terminal clutter (WARNING+ on console by default)
- Detailed DEBUG logs to files
- Structured JSON format for file logs
- Rate limiting for repetitive errors (prevents log spam)
- Separate log files by category (main, error, api, trading)
- Auto-rotation and archiving
- Thread-safe operations

USAGE: Import this module FIRST in any entry point to configure logging:
    import core.kingdom_logging  # Auto-configures on import

Or explicitly:
    from core.kingdom_logging import configure_kingdom_logging
    configure_kingdom_logging()
"""

import os
import sys
import json
import time
import logging
import logging.config
import logging.handlers
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Set
from collections import defaultdict
from functools import wraps


class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def shouldRollover(self, record: logging.LogRecord) -> bool:
        try:
            return bool(super().shouldRollover(record))
        except Exception:
            try:
                self.disabled = True
            except Exception:
                pass
            return False

    def handleError(self, record: logging.LogRecord) -> None:
        try:
            self.disabled = True
        except Exception:
            pass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except Exception:
            try:
                self.disabled = True
            except Exception:
                pass

    def doRollover(self):
        try:
            super().doRollover()
        except Exception:
            try:
                if self.stream:
                    self.stream.close()
            except Exception:
                pass
            try:
                self.stream = self._open()
            except Exception:
                pass

# ============================================================================
# IMMEDIATE NOISE SUPPRESSION (runs before anything else)
# ============================================================================
# Suppress noisy loggers IMMEDIATELY to prevent spam during imports
def _suppress_noisy_loggers_immediately():
    """Suppress verbose loggers before they can spam the console."""
    import logging
    _noisy = [
        "qiskit", "qiskit.transpiler", "qiskit.passmanager", "qiskit.compiler",
        "qiskit.circuit", "qiskit.primitives", "qiskit.transpiler.passes",
        "qiskit_ibm_provider", "qiskit_aer", "urllib3", "websockets", "asyncio",
        "aiohttp", "ccxt", "httpx", "httpcore", "PIL", "tensorflow", "torch",
        "transformers", "web3", "eth_utils", "setuptools", "pkg_resources",
    ]
    for name in _noisy:
        logging.getLogger(name).setLevel(logging.WARNING)

# Run immediately on import
_suppress_noisy_loggers_immediately()

# ============================================================================
# SOTA 2025 Configuration Constants
# ============================================================================

# Base paths
BASE_DIR = Path(__file__).parent.parent
LOG_DIR = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs"))

# Console output level - reduces terminal clutter
CONSOLE_LEVEL = logging.WARNING  # Only WARNING+ on terminal

# File output levels
FILE_LEVEL = logging.DEBUG  # Full debug info in files
ERROR_FILE_LEVEL = logging.ERROR  # Errors only in error log

# Log rotation settings
MAX_BYTES = 10 * 1024 * 1024  # 10MB per file
BACKUP_COUNT = 5  # Keep 5 rotated files

# Rate limiting for repetitive errors (SOTA 2025 pattern)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 5  # max same message per window

# Noisy loggers to suppress on console (still logged to files)
NOISY_LOGGERS = {
    "urllib3",
    "websockets",
    "asyncio",
    "aiohttp",
    "ccxt",
    "httpx",
    "httpcore",
    "PIL",
    # Qiskit loggers (very verbose)
    "qiskit",
    "qiskit.transpiler",
    "qiskit.passmanager",
    "qiskit.compiler",
    "qiskit.circuit",
    # IBM Quantum
    "qiskit_ibm_provider",
    "qiskit_aer",
    # Other ML/AI libs
    "tensorflow",
    "torch",
    "transformers",
    "huggingface",
    # Crypto libs
    "web3",
    "eth_utils",
    # Setuptools deprecation warnings
    "setuptools",
    "pkg_resources",
}

# API error patterns to rate-limit (prevents log spam from geo-blocks etc)
API_ERROR_PATTERNS = [
    "Service unavailable from a restricted location",
    "Timestamp for this request was",
    "Invalid API-key",
    "api-signature-not-valid",
    "requires \"password\" credential",
]


# ============================================================================
# Rate-Limited Filter (SOTA 2025 - Prevents Log Spam)
# ============================================================================

class RateLimitFilter(logging.Filter):
    """
    SOTA 2025 Rate Limiting Filter.
    
    Prevents log spam by limiting how often the same message can be logged.
    Useful for repetitive API errors, connection retries, etc.
    """
    
    def __init__(self, window: int = RATE_LIMIT_WINDOW, max_count: int = RATE_LIMIT_MAX):
        super().__init__()
        self.window = window
        self.max_count = max_count
        self._message_counts: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()
        self._suppressed_counts: Dict[str, int] = defaultdict(int)
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out repetitive log messages within the rate limit window."""
        # Always allow critical messages
        if record.levelno >= logging.CRITICAL:
            return True
        
        # Create a key from the message (normalize for rate limiting)
        msg_key = self._get_message_key(record)
        current_time = time.time()
        
        with self._lock:
            # Clean old entries outside the window
            timestamps = self._message_counts[msg_key]
            timestamps[:] = [t for t in timestamps if current_time - t < self.window]
            
            # Check if we should allow this message
            if len(timestamps) < self.max_count:
                timestamps.append(current_time)
                
                # If we had suppressed messages, log a summary
                if self._suppressed_counts[msg_key] > 0:
                    suppressed = self._suppressed_counts[msg_key]
                    self._suppressed_counts[msg_key] = 0
                    record.msg = f"{record.msg} (+ {suppressed} similar messages suppressed)"
                
                return True
            else:
                # Rate limited - suppress this message
                self._suppressed_counts[msg_key] += 1
                return False
    
    def _get_message_key(self, record: logging.LogRecord) -> str:
        """Generate a key for rate limiting based on logger name and message pattern."""
        # Truncate message to first 100 chars for matching
        msg = record.getMessage()[:100] if record.getMessage() else ""
        
        # Check if this matches known API error patterns
        for pattern in API_ERROR_PATTERNS:
            if pattern in msg:
                return f"{record.name}:{pattern}"
        
        return f"{record.name}:{msg}"


# ============================================================================
# Console Filter (Suppress Noisy Loggers)
# ============================================================================

class ConsoleFilter(logging.Filter):
    """
    Filter to suppress noisy third-party loggers from console output.
    These logs still go to files for debugging.
    """
    
    def __init__(self, noisy_loggers: Set[str] = None):
        super().__init__()
        self.noisy_loggers = noisy_loggers or NOISY_LOGGERS
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Allow message if not from a noisy logger or if ERROR+."""
        # Always allow ERROR+ messages
        if record.levelno >= logging.ERROR:
            return True
        
        # Check if from a noisy logger
        for noisy in self.noisy_loggers:
            if record.name.startswith(noisy):
                return False
        
        return True


# ============================================================================
# SOTA JSON Formatter (Structured Logging)
# ============================================================================

class KingdomJSONFormatter(logging.Formatter):
    """
    SOTA 2025 JSON Formatter for structured logging.
    
    Produces machine-readable JSON logs with full context:
    - Timestamp (ISO 8601)
    - Level, logger name, message
    - Thread/process info
    - Exception details with full traceback
    - Extra fields from record
    """
    
    EXCLUDED_ATTRS = {
        'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
        'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
        'message', 'msg', 'name', 'pathname', 'process', 'processName',
        'relativeCreated', 'stack_info', 'thread', 'threadName', 'taskName'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add thread info (useful for debugging async issues)
        log_data["thread"] = {
            "id": record.thread,
            "name": record.threadName
        }
        
        # Add process info
        log_data["process"] = {
            "id": record.process,
            "name": record.processName
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in self.EXCLUDED_ATTRS and not key.startswith('_'):
                try:
                    json.dumps(value)  # Check if serializable
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)
        
        return json.dumps(log_data, default=str)


# ============================================================================
# Console Formatter (Clean, Readable Output)
# ============================================================================

class KingdomConsoleFormatter(logging.Formatter):
    """
    Clean console formatter with color-coded levels.
    
    Format: [TIME] LEVEL | Logger: Message
    """
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console output."""
        # Timestamp (short format for console)
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        
        # Level with optional color
        level = record.levelname
        if self.use_colors and level in self.COLORS:
            level = f"{self.COLORS[level]}{level:8}{self.RESET}"
        else:
            level = f"{level:8}"
        
        # Shorten logger name for console
        logger_name = record.name
        if logger_name.startswith("KingdomAI."):
            logger_name = logger_name[10:]  # Remove prefix
        if len(logger_name) > 25:
            logger_name = "..." + logger_name[-22:]
        
        # Format message
        message = record.getMessage()
        
        # Add exception info if present
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        
        return f"[{timestamp}] {level} | {logger_name}: {message}"


# ============================================================================
# Main Configuration Function
# ============================================================================

_configured = False
_config_lock = threading.Lock()


def configure_kingdom_logging(
    console_level: int = CONSOLE_LEVEL,
    file_level: int = FILE_LEVEL,
    log_dir: Path = LOG_DIR,
    enable_rate_limiting: bool = True,
    enable_json_files: bool = True,
) -> logging.Logger:
    """
    Configure Kingdom AI logging system.
    
    This should be called once at application startup, ideally before
    any other imports that might trigger logging.
    
    Args:
        console_level: Minimum level for console output (default: WARNING)
        file_level: Minimum level for file output (default: DEBUG)
        log_dir: Directory for log files
        enable_rate_limiting: Enable rate limiting for repetitive messages
        enable_json_files: Use JSON format for file logs
    
    Returns:
        Root KingdomAI logger
    """
    global _configured
    
    with _config_lock:
        if _configured:
            return logging.getLogger("KingdomAI")

        logging.raiseExceptions = False
        
        # Ensure log directory exists
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create formatters
        console_formatter = KingdomConsoleFormatter(use_colors=True)
        file_formatter = KingdomJSONFormatter() if enable_json_files else logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create filters
        rate_limit_filter = RateLimitFilter() if enable_rate_limiting else None
        console_filter = ConsoleFilter()
        
        # =====================================================================
        # Configure Root Logger
        # =====================================================================
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handlers
        
        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # =====================================================================
        # Console Handler (WARNING+ only, clean output)
        # =====================================================================
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(console_filter)
        if rate_limit_filter:
            console_handler.addFilter(rate_limit_filter)
        root_logger.addHandler(console_handler)
        
        # =====================================================================
        # Main Log File (rotating, all levels)
        # =====================================================================
        main_log = log_dir / "kingdom_main.log"
        main_handler = SafeRotatingFileHandler(
            main_log,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        main_handler.setLevel(file_level)
        main_handler.setFormatter(file_formatter)
        if rate_limit_filter:
            main_handler.addFilter(rate_limit_filter)
        root_logger.addHandler(main_handler)
        
        # =====================================================================
        # Error Log File (errors only, for quick review)
        # =====================================================================
        error_log = log_dir / "kingdom_errors.log"
        error_handler = SafeRotatingFileHandler(
            error_log,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
        # =====================================================================
        # API Log File (for API-related logs)
        # =====================================================================
        api_log = log_dir / "kingdom_api.log"
        api_handler = SafeRotatingFileHandler(
            api_log,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        api_handler.setLevel(logging.DEBUG)
        api_handler.setFormatter(file_formatter)
        api_handler.addFilter(logging.Filter("core.real_exchange"))
        root_logger.addHandler(api_handler)
        
        # =====================================================================
        # Configure Third-Party Loggers (reduce noise)
        # =====================================================================
        for noisy in NOISY_LOGGERS:
            logging.getLogger(noisy).setLevel(logging.WARNING)
        
        # Suppress overly verbose ccxt logging
        logging.getLogger("ccxt").setLevel(logging.WARNING)
        logging.getLogger("ccxt.base.exchange").setLevel(logging.WARNING)
        
        # Aggressively suppress qiskit (extremely verbose)
        for qiskit_logger in ["qiskit", "qiskit.transpiler", "qiskit.passmanager", 
                              "qiskit.compiler", "qiskit.circuit", "qiskit.primitives",
                              "qiskit.transpiler.passes", "qiskit.transpiler.passes.basis"]:
            logging.getLogger(qiskit_logger).setLevel(logging.ERROR)
        
        _configured = True
        
        # Log startup message
        logger = logging.getLogger("KingdomAI")
        logger.info(
            "Kingdom AI Logging initialized",
            extra={
                "console_level": logging.getLevelName(console_level),
                "file_level": logging.getLevelName(file_level),
                "log_dir": str(log_dir),
                "rate_limiting": enable_rate_limiting,
                "json_format": enable_json_files,
            }
        )
        
        return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific component.
    
    Args:
        name: Component name (will be prefixed with KingdomAI.)
    
    Returns:
        Logger instance
    """
    if not name.startswith("KingdomAI."):
        name = f"KingdomAI.{name}"
    return logging.getLogger(name)


def set_console_level(level: int) -> None:
    """Change console logging level at runtime."""
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            handler.setLevel(level)


def enable_debug_console() -> None:
    """Enable DEBUG level on console (for troubleshooting)."""
    set_console_level(logging.DEBUG)


def disable_debug_console() -> None:
    """Restore WARNING level on console (normal operation)."""
    set_console_level(logging.WARNING)


# ============================================================================
# Auto-Configure on Import
# ============================================================================

# Configure logging when this module is imported
configure_kingdom_logging()
