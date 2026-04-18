#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ERROR TRACKER - SOTA 2026 Comprehensive Error & Hang Detection System

This module tracks:
- ALL errors that occur during runtime
- BLOCKING/HANGING operations (operations that take too long)
- SLOW operations (close to timeout)
- Operation timing and status

SOTA 2026 Features:
- Hang detection via operation timeouts
- System status dashboard
- Categorized error tracking
- Rate limiting for spam prevention
"""

import logging
import logging.handlers
import traceback
import sys
import os
import time
import asyncio
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
from enum import Enum
import json
import threading

# ============================================================================
# SOTA 2026: Operation Status Enum
# ============================================================================

class OperationStatus(Enum):
    PENDING = "⏳ PENDING"
    RUNNING = "🔄 RUNNING"
    SUCCESS = "✅ SUCCESS"
    SLOW = "⚠️ SLOW"
    TIMEOUT = "🔴 TIMEOUT"
    FAILED = "❌ FAILED"
    BLOCKED = "🔴 BLOCKED"


# Operation timeout defaults (seconds)
OPERATION_TIMEOUTS = {
    "default": 10.0,
    "redis": 5.0,
    "database": 5.0,
    "api": 10.0,
    "blockchain": 15.0,
    "gui": 30.0,
    "voice": 10.0,
    "ai": 60.0,
}


class ErrorTracker:
    """SOTA 2026 Centralized error tracking system with hang detection"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Create logs directory
        self.logs_dir = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs"))
        try:
            if self.logs_dir.exists() and not self.logs_dir.is_dir():
                backup_path = self.logs_dir.with_name(
                    f"logs_file_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                )
                try:
                    self.logs_dir.rename(backup_path)
                except Exception:
                    try:
                        if self.logs_dir.stat().st_size == 0:
                            self.logs_dir.unlink()
                        else:
                            backup_path.write_bytes(self.logs_dir.read_bytes())
                            self.logs_dir.unlink()
                    except Exception:
                        pass
        except Exception:
            pass
        self.logs_dir.mkdir(exist_ok=True)
        
        # Session timestamp
        self.session_start = datetime.now()
        self.session_id = self.session_start.strftime("%Y%m%d_%H%M%S")
        
        # Error tracking
        self.error_counts = defaultdict(int)
        self.error_details = []
        self.unique_errors = {}
        
        # SOTA 2026: Operation tracking for hang detection
        self.operations: List[Dict[str, Any]] = []
        self.blocked_operations: List[Dict[str, Any]] = []
        self.slow_operations: List[Dict[str, Any]] = []
        self.failed_operations: List[Dict[str, Any]] = []
        self.component_status: Dict[str, Dict[str, Any]] = {}
        
        # SOTA 2026: Warnings/Errors Indexer (initialized later to avoid circular ref)
        self.indexer: Optional['WarningsErrorsIndexer'] = None
        
        # Log files
        self.error_log_file = self.logs_dir / f"errors_{self.session_id}.log"
        self.error_summary_file = self.logs_dir / "error_summary.txt"
        self.error_json_file = self.logs_dir / f"errors_{self.session_id}.json"
        self.dashboard_file = self.logs_dir / "SYSTEM_DASHBOARD.txt"
        self.status_file = self.logs_dir / f"system_status_{self.session_id}.json"
        
        # Initialize files
        self._init_log_files()
        
        # Purge old session files — keep only the 3 most recent per type
        self._purge_old_session_files()
        
        # Set up exception hook
        self._setup_exception_hook()
        
        print(f"✅ Error Tracker initialized - Session: {self.session_id}")
        print(f"📁 Error logs: {self.error_log_file}")
        print(f"📊 Error summary: {self.error_summary_file}")
        print(f"📊 System dashboard: {self.dashboard_file}")
    
    def _init_log_files(self):
        """Initialize log files with headers"""
        with open(self.error_log_file, 'w') as f:
            f.write(f"KINGDOM AI ERROR LOG - Session: {self.session_id}\n")
            f.write(f"Started: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
        
        with open(self.error_summary_file, 'w') as f:
            f.write(f"KINGDOM AI ERROR SUMMARY - Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
    
    def _purge_old_session_files(self):
        """Remove old session log files, keeping only the 3 most recent per type."""
        try:
            import glob
            patterns = ['errors_*.log', 'errors_*.json', 'system_status_*.json',
                        'all_logs_*.log', 'stdout_*.log', 'stderr_*.log',
                        'warnings_errors_index_*.txt']
            for pattern in patterns:
                files = sorted(
                    glob.glob(str(self.logs_dir / pattern)),
                    key=lambda f: os.path.getmtime(f),
                    reverse=True
                )
                for old_file in files[3:]:
                    try:
                        os.remove(old_file)
                    except Exception:
                        pass
        except Exception:
            pass

    def _setup_exception_hook(self):
        """Set up global exception hook to catch all unhandled exceptions"""
        original_excepthook = sys.excepthook
        
        def custom_excepthook(exc_type, exc_value, exc_traceback):
            # Track the error
            self.track_exception(exc_type, exc_value, exc_traceback)
            # Call original handler
            original_excepthook(exc_type, exc_value, exc_traceback)
        
        sys.excepthook = custom_excepthook
    
    def track_error(self, error_type: str, error_msg: str, location: str = "", 
                   traceback_str: str = "", severity: str = "ERROR"):
        """Track an error with details
        
        Args:
            error_type: Type of error (e.g., 'ImportError', 'AttributeError')
            error_msg: Error message
            location: Where the error occurred (file:line)
            traceback_str: Full traceback string
            severity: ERROR, WARNING, CRITICAL
        """
        timestamp = datetime.now()
        
        # Create error signature for deduplication
        error_signature = f"{error_type}:{error_msg}:{location}"
        
        # Count this error
        self.error_counts[error_signature] += 1
        
        # Store unique error details
        if error_signature not in self.unique_errors:
            self.unique_errors[error_signature] = {
                'type': error_type,
                'message': error_msg,
                'location': location,
                'first_seen': timestamp.isoformat(),
                'count': 0,
                'severity': severity,
                'traceback': traceback_str
            }
        
        self.unique_errors[error_signature]['count'] = self.error_counts[error_signature]
        self.unique_errors[error_signature]['last_seen'] = timestamp.isoformat()
        
        # Log to file
        self._write_error_to_log(timestamp, error_type, error_msg, location, 
                                traceback_str, severity, self.error_counts[error_signature])
        
        # Update summary
        self._update_summary()
        
        # Save JSON
        self._save_json()
    
    def track_exception(self, exc_type, exc_value, exc_traceback):
        """Track an exception with full traceback"""
        error_type = exc_type.__name__
        error_msg = str(exc_value)
        
        # Extract location from traceback
        location = "unknown"
        if exc_traceback:
            tb_frame = traceback.extract_tb(exc_traceback)[-1]
            location = f"{tb_frame.filename}:{tb_frame.lineno}"
        
        # Get full traceback
        traceback_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        self.track_error(error_type, error_msg, location, traceback_str, "CRITICAL")
    
    def _write_error_to_log(self, timestamp, error_type, error_msg, location, 
                           traceback_str, severity, count):
        """Write error to log file"""
        with open(self.error_log_file, 'a') as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {severity}: {error_type}\n")
            f.write(f"Count: {count}\n")
            f.write(f"Location: {location}\n")
            f.write(f"Message: {error_msg}\n")
            if traceback_str:
                f.write(f"\nTraceback:\n{traceback_str}\n")
            f.write(f"{'=' * 80}\n")
    
    def _update_summary(self):
        """Update the error summary file"""
        with open(self.error_summary_file, 'w') as f:
            f.write(f"KINGDOM AI ERROR SUMMARY\n")
            f.write(f"Session: {self.session_id}\n")
            f.write(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            # Total counts
            total_errors = sum(self.error_counts.values())
            unique_errors = len(self.unique_errors)
            
            f.write(f"📊 STATISTICS:\n")
            f.write(f"  Total Errors: {total_errors}\n")
            f.write(f"  Unique Errors: {unique_errors}\n")
            f.write(f"\n{'=' * 80}\n\n")
            
            # Sort errors by count (most frequent first)
            sorted_errors = sorted(
                self.unique_errors.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )
            
            f.write(f"🔴 TOP ERRORS (by frequency):\n\n")
            
            for i, (signature, details) in enumerate(sorted_errors[:50], 1):
                f.write(f"{i}. [{details['severity']}] {details['type']}\n")
                f.write(f"   Count: {details['count']}\n")
                f.write(f"   Location: {details['location']}\n")
                f.write(f"   Message: {details['message'][:200]}\n")
                f.write(f"   First seen: {details['first_seen']}\n")
                f.write(f"   Last seen: {details['last_seen']}\n")
                f.write(f"\n{'-' * 80}\n\n")
            
            # Group by error type
            f.write(f"\n{'=' * 80}\n\n")
            f.write(f"📋 ERRORS BY TYPE:\n\n")
            
            errors_by_type = defaultdict(list)
            for signature, details in self.unique_errors.items():
                errors_by_type[details['type']].append(details)
            
            for error_type, errors in sorted(errors_by_type.items()):
                total_count = sum(e['count'] for e in errors)
                f.write(f"\n{error_type}: {total_count} occurrences ({len(errors)} unique)\n")
                for error in sorted(errors, key=lambda x: x['count'], reverse=True)[:5]:
                    f.write(f"  - {error['message'][:100]} (x{error['count']})\n")
    
    def _save_json(self):
        """Save error data as JSON for programmatic access"""
        data = {
            'session_id': self.session_id,
            'session_start': self.session_start.isoformat(),
            'last_updated': datetime.now().isoformat(),
            'total_errors': sum(self.error_counts.values()),
            'unique_errors': len(self.unique_errors),
            'errors': list(self.unique_errors.values())
        }
        
        with open(self.error_json_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_summary(self) -> str:
        """Get a brief summary of errors"""
        total = sum(self.error_counts.values())
        unique = len(self.unique_errors)
        
        summary = f"\n{'=' * 80}\n"
        summary += f"ERROR TRACKER SUMMARY - Session: {self.session_id}\n"
        summary += f"{'=' * 80}\n"
        summary += f"Total Errors: {total}\n"
        summary += f"Unique Errors: {unique}\n"
        summary += f"\nLog files:\n"
        summary += f"  - Detailed log: {self.error_log_file}\n"
        summary += f"  - Summary: {self.error_summary_file}\n"
        summary += f"  - JSON data: {self.error_json_file}\n"
        summary += f"{'=' * 80}\n"
        
        return summary
    
    def print_summary(self):
        """Print summary to console"""
        print(self.get_summary())
    
    def get_top_errors(self, n: int = 10) -> List[Dict]:
        """Get the top N most frequent errors"""
        sorted_errors = sorted(
            self.unique_errors.values(),
            key=lambda x: x['count'],
            reverse=True
        )
        return sorted_errors[:n]
    
    # ========================================================================
    # SOTA 2026: Operation Tracking & Hang Detection
    # ========================================================================
    
    def track_operation(self, name: str, status: OperationStatus, duration: float = 0,
                       error: str = None, timeout: float = None):
        """Track an operation with timing and status"""
        op = {
            "name": name,
            "status": status.value,
            "duration": round(duration, 2),
            "timeout": timeout,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self.operations.append(op)
        
        # Categorize
        if status in (OperationStatus.BLOCKED, OperationStatus.TIMEOUT):
            self.blocked_operations.append(op)
            self._log_blocked(op)
        elif status == OperationStatus.SLOW:
            self.slow_operations.append(op)
        elif status == OperationStatus.FAILED:
            self.failed_operations.append(op)
        
        # Keep last 1000 operations
        if len(self.operations) > 1000:
            self.operations = self.operations[-500:]
        
        self._write_dashboard()
        self._save_status_json()
    
    def update_component(self, name: str, status: OperationStatus, details: str = ""):
        """Update component status"""
        self.component_status[name] = {
            "name": name,
            "status": status.value,
            "details": details,
            "last_update": datetime.now().isoformat()
        }
        self._write_dashboard()
    
    def _log_blocked(self, op: Dict):
        """Log a blocked operation to error log"""
        with open(self.error_log_file, 'a') as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"[{op['timestamp']}] 🔴 BLOCKED/TIMEOUT OPERATION\n")
            f.write(f"Operation: {op['name']}\n")
            f.write(f"Duration: {op['duration']}s (timeout: {op['timeout']}s)\n")
            if op.get('error'):
                f.write(f"Error: {op['error']}\n")
            f.write(f"{'=' * 80}\n")
    
    def _write_dashboard(self):
        """Write human-readable system status dashboard"""
        try:
            with open(self.dashboard_file, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write("🏰 KINGDOM AI - SYSTEM STATUS DASHBOARD\n")
                f.write(f"Session: {self.session_id} | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                
                # Summary
                f.write("📊 SUMMARY\n")
                f.write("-" * 40 + "\n")
                f.write(f"  🔴 BLOCKED/TIMEOUT: {len(self.blocked_operations)}\n")
                f.write(f"  ⚠️ SLOW: {len(self.slow_operations)}\n")
                f.write(f"  ❌ FAILED: {len(self.failed_operations)}\n")
                f.write(f"  ❌ ERRORS: {sum(self.error_counts.values())}\n")
                f.write(f"  📦 Components: {len(self.component_status)}\n\n")
                
                # Components
                if self.component_status:
                    f.write("📦 COMPONENT STATUS\n")
                    f.write("-" * 40 + "\n")
                    for name, comp in sorted(self.component_status.items()):
                        f.write(f"  {comp['status']} {name}\n")
                        if comp.get('details'):
                            f.write(f"      {comp['details']}\n")
                    f.write("\n")
                
                # Blocked operations
                if self.blocked_operations:
                    f.write("🔴 BLOCKED/TIMEOUT OPERATIONS (NEEDS ATTENTION!)\n")
                    f.write("-" * 40 + "\n")
                    for op in self.blocked_operations[-20:]:
                        f.write(f"  [{op['timestamp']}] {op['name']}\n")
                        f.write(f"      Duration: {op['duration']}s (timeout: {op['timeout']}s)\n")
                        if op.get('error'):
                            f.write(f"      Error: {op['error'][:100]}\n")
                    f.write("\n")
                
                # Top errors
                if self.unique_errors:
                    f.write("❌ TOP ERRORS\n")
                    f.write("-" * 40 + "\n")
                    for err in self.get_top_errors(5):
                        f.write(f"  [{err['severity']}] {err['type']}: {err['message'][:80]}\n")
                        f.write(f"      Count: {err['count']} | Location: {err['location']}\n")
                    f.write("\n")
                
                f.write("=" * 80 + "\n")
                f.write(f"Log files in: {self.logs_dir}/\n")
                f.write("=" * 80 + "\n")
        except Exception:
            pass
    
    def _save_status_json(self):
        """Save status as JSON"""
        try:
            data = {
                "session_id": self.session_id,
                "last_update": datetime.now().isoformat(),
                "blocked_count": len(self.blocked_operations),
                "slow_count": len(self.slow_operations),
                "failed_count": len(self.failed_operations),
                "error_count": sum(self.error_counts.values()),
                "components": self.component_status,
                "recent_blocked": self.blocked_operations[-10:],
                "recent_failed": self.failed_operations[-10:]
            }
            with open(self.status_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
    
    def get_dashboard(self) -> str:
        """Get dashboard as string"""
        try:
            with open(self.dashboard_file, 'r') as f:
                return f.read()
        except Exception:
            return "Dashboard not available"


# Global error tracker instance
_error_tracker = None

def get_error_tracker() -> ErrorTracker:
    """Get the global error tracker instance"""
    global _error_tracker
    if _error_tracker is None:
        _error_tracker = ErrorTracker()
    return _error_tracker


def track_error(error_type: str, error_msg: str, location: str = "", 
               traceback_str: str = "", severity: str = "ERROR"):
    """Convenience function to track an error"""
    tracker = get_error_tracker()
    tracker.track_error(error_type, error_msg, location, traceback_str, severity)


# ============================================================================
# SOTA 2026: Async Operation Tracking with Hang Detection
# ============================================================================

async def track_async_operation(name: str, coro, timeout: float = None, 
                                logger: logging.Logger = None):
    """
    Track an async operation with timeout and hang detection.
    
    This catches blocking/hanging operations that exceptions don't catch.
    
    Args:
        name: Operation name for logging
        coro: Coroutine to execute
        timeout: Timeout in seconds (default from OPERATION_TIMEOUTS)
        logger: Logger to use (optional)
    
    Returns:
        Result of the coroutine
        
    Raises:
        asyncio.TimeoutError: If operation times out
    """
    # Get timeout from defaults if not specified
    if timeout is None:
        # Check for category match
        name_lower = name.lower()
        for key, val in OPERATION_TIMEOUTS.items():
            if key in name_lower:
                timeout = val
                break
        else:
            timeout = OPERATION_TIMEOUTS["default"]
    
    tracker = get_error_tracker()
    _logger = logger or logging.getLogger("OperationTracker")
    
    start_time = time.time()
    tracker.update_component(name, OperationStatus.RUNNING)
    
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        duration = time.time() - start_time
        
        if duration > timeout * 0.8:
            # Close to timeout - mark as slow
            status = OperationStatus.SLOW
            _logger.warning(f"⚠️ {name} was SLOW: {duration:.2f}s (limit: {timeout}s)")
        else:
            status = OperationStatus.SUCCESS
            _logger.debug(f"✅ {name} completed in {duration:.2f}s")
        
        tracker.update_component(name, status)
        tracker.track_operation(name, status, duration, None, timeout)
        return result
        
    except asyncio.TimeoutError:
        duration = time.time() - start_time
        _logger.error(f"🔴 TIMEOUT: {name} timed out after {timeout}s")
        tracker.update_component(name, OperationStatus.TIMEOUT, f"Timed out after {timeout}s")
        tracker.track_operation(name, OperationStatus.TIMEOUT, duration, "Operation timed out", timeout)
        raise
        
    except Exception as e:
        duration = time.time() - start_time
        _logger.error(f"❌ {name} FAILED after {duration:.2f}s: {e}")
        tracker.update_component(name, OperationStatus.FAILED, str(e))
        tracker.track_operation(name, OperationStatus.FAILED, duration, str(e), timeout)
        raise


def log_component_status(name: str, status: str, details: str = ""):
    """Log a component status update"""
    tracker = get_error_tracker()
    logger = logging.getLogger("ComponentStatus")
    
    if "SUCCESS" in status.upper() or "✅" in status:
        tracker.update_component(name, OperationStatus.SUCCESS, details)
        logger.info(f"✅ {name}: {details or 'initialized'}")
    elif "FAILED" in status.upper() or "❌" in status:
        tracker.update_component(name, OperationStatus.FAILED, details)
        logger.error(f"❌ {name}: {details or 'failed'}")
    elif "SLOW" in status.upper() or "⚠️" in status:
        tracker.update_component(name, OperationStatus.SLOW, details)
        logger.warning(f"⚠️ {name}: {details or 'slow'}")
    elif "TIMEOUT" in status.upper() or "🔴" in status:
        tracker.update_component(name, OperationStatus.TIMEOUT, details)
        logger.error(f"🔴 {name}: {details or 'timeout'}")
    else:
        tracker.update_component(name, OperationStatus.RUNNING, details)
        logger.info(f"🔄 {name}: {details or 'running'}")


def print_dashboard():
    """Print the system status dashboard"""
    print(get_error_tracker().get_dashboard())


# ============================================================================
# SOTA 2026: Automated Warnings/Errors Indexer
# ============================================================================

class WarningsErrorsIndexer:
    """SOTA 2026: Automated indexer that lists all warnings and errors by module."""
    
    def __init__(self, tracker: 'ErrorTracker'):
        self.tracker = tracker
        self.warnings: Dict[str, List[Dict]] = {}  # module -> list of warnings
        self.errors: Dict[str, List[Dict]] = {}    # module -> list of errors
        self.summary_file = tracker.logs_dir / f"warnings_errors_index_{tracker.session_id}.txt"
        self._lock = threading.Lock()
    
    def add_warning(self, module: str, message: str, location: str = "", count: int = 1):
        """Add a warning to the index."""
        with self._lock:
            if module not in self.warnings:
                self.warnings[module] = []
            
            # Check for existing warning with same message
            for w in self.warnings[module]:
                if w['message'] == message:
                    w['count'] += count
                    w['last_seen'] = datetime.now().isoformat()
                    return
            
            self.warnings[module].append({
                'message': message,
                'location': location,
                'count': count,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat()
            })
    
    def add_error(self, module: str, error_type: str, message: str, location: str = "", count: int = 1):
        """Add an error to the index."""
        with self._lock:
            if module not in self.errors:
                self.errors[module] = []
            
            # Check for existing error with same message
            for e in self.errors[module]:
                if e['message'] == message and e['type'] == error_type:
                    e['count'] += count
                    e['last_seen'] = datetime.now().isoformat()
                    return
            
            self.errors[module].append({
                'type': error_type,
                'message': message,
                'location': location,
                'count': count,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat()
            })
    
    def get_module_from_logger(self, logger_name: str) -> str:
        """Extract module category from logger name."""
        name_lower = logger_name.lower()
        
        # Map to system categories
        if 'trading' in name_lower:
            return 'TRADING'
        elif 'mining' in name_lower:
            return 'MINING'
        elif 'blockchain' in name_lower or 'web3' in name_lower:
            return 'BLOCKCHAIN'
        elif 'wallet' in name_lower:
            return 'WALLET'
        elif 'thoth' in name_lower or 'brain' in name_lower:
            return 'THOTH_AI'
        elif 'redis' in name_lower or 'nexus' in name_lower:
            return 'REDIS'
        elif 'voice' in name_lower or 'speech' in name_lower or 'tts' in name_lower:
            return 'VOICE'
        elif 'sentience' in name_lower or 'consciousness' in name_lower:
            return 'SENTIENCE'
        elif 'vr' in name_lower:
            return 'VR'
        elif 'gui' in name_lower or 'qt' in name_lower:
            return 'GUI'
        elif 'api' in name_lower and 'key' in name_lower:
            return 'API_KEYS'
        elif 'websocket' in name_lower or 'ws' in name_lower:
            return 'WEBSOCKET'
        elif 'event' in name_lower:
            return 'EVENT_BUS'
        else:
            return logger_name.split('.')[0] if '.' in logger_name else 'SYSTEM'
    
    def write_summary(self):
        """Write a comprehensive summary file of all warnings and errors."""
        try:
            with open(self.summary_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("🏰 KINGDOM AI - WARNINGS & ERRORS INDEX\n")
                f.write(f"Session: {self.tracker.session_id}\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                
                # Statistics
                total_warnings = sum(sum(w['count'] for w in ws) for ws in self.warnings.values())
                total_errors = sum(sum(e['count'] for e in es) for es in self.errors.values())
                unique_warnings = sum(len(ws) for ws in self.warnings.values())
                unique_errors = sum(len(es) for es in self.errors.values())
                
                f.write("📊 STATISTICS\n")
                f.write("-" * 40 + "\n")
                f.write(f"  ⚠️ Total Warnings: {total_warnings} ({unique_warnings} unique)\n")
                f.write(f"  ❌ Total Errors: {total_errors} ({unique_errors} unique)\n")
                f.write(f"  📦 Modules with warnings: {len(self.warnings)}\n")
                f.write(f"  📦 Modules with errors: {len(self.errors)}\n")
                f.write("\n")
                
                # Errors by module (priority)
                if self.errors:
                    f.write("=" * 80 + "\n")
                    f.write("❌ ERRORS BY MODULE\n")
                    f.write("=" * 80 + "\n\n")
                    
                    for module in sorted(self.errors.keys()):
                        errors = self.errors[module]
                        module_total = sum(e['count'] for e in errors)
                        f.write(f"📦 {module} ({module_total} errors)\n")
                        f.write("-" * 40 + "\n")
                        
                        for err in sorted(errors, key=lambda x: x['count'], reverse=True):
                            f.write(f"  [{err['type']}] x{err['count']}\n")
                            f.write(f"    Message: {err['message'][:200]}\n")
                            if err['location']:
                                f.write(f"    Location: {err['location']}\n")
                            f.write(f"    First: {err['first_seen']}\n")
                            f.write("\n")
                        f.write("\n")
                
                # Warnings by module
                if self.warnings:
                    f.write("=" * 80 + "\n")
                    f.write("⚠️ WARNINGS BY MODULE\n")
                    f.write("=" * 80 + "\n\n")
                    
                    for module in sorted(self.warnings.keys()):
                        warnings = self.warnings[module]
                        module_total = sum(w['count'] for w in warnings)
                        f.write(f"📦 {module} ({module_total} warnings)\n")
                        f.write("-" * 40 + "\n")
                        
                        for warn in sorted(warnings, key=lambda x: x['count'], reverse=True):
                            f.write(f"  x{warn['count']}: {warn['message'][:200]}\n")
                            if warn['location']:
                                f.write(f"    Location: {warn['location']}\n")
                            f.write("\n")
                        f.write("\n")
                
                f.write("=" * 80 + "\n")
                f.write("END OF INDEX\n")
                f.write("=" * 80 + "\n")
                
        except Exception as e:
            logging.getLogger("ErrorTracker").error(f"Failed to write warnings/errors index: {e}")
    
    def get_summary_dict(self) -> Dict:
        """Get summary as dictionary for programmatic access."""
        return {
            'warnings': dict(self.warnings),
            'errors': dict(self.errors),
            'stats': {
                'total_warnings': sum(sum(w['count'] for w in ws) for ws in self.warnings.values()),
                'total_errors': sum(sum(e['count'] for e in es) for es in self.errors.values()),
                'unique_warnings': sum(len(ws) for ws in self.warnings.values()),
                'unique_errors': sum(len(es) for es in self.errors.values()),
                'modules_with_warnings': len(self.warnings),
                'modules_with_errors': len(self.errors)
            }
        }


# Custom logging handler that tracks errors AND warnings
class ErrorTrackingHandler(logging.Handler):
    """Logging handler that sends errors and warnings to the error tracker"""
    
    def emit(self, record):
        if record.levelno >= logging.WARNING:
            tracker = get_error_tracker()
            
            # Extract location
            location = f"{record.pathname}:{record.lineno}"
            
            # Get traceback if available
            traceback_str = ""
            if record.exc_info:
                traceback_str = ''.join(traceback.format_exception(*record.exc_info))
            
            # Determine severity
            severity = "ERROR"
            if record.levelno >= logging.CRITICAL:
                severity = "CRITICAL"
            elif record.levelno >= logging.ERROR:
                severity = "ERROR"
            elif record.levelno >= logging.WARNING:
                severity = "WARNING"
            
            # SOTA 2026: Also track in warnings/errors indexer
            if hasattr(tracker, 'indexer') and tracker.indexer is not None:
                module = tracker.indexer.get_module_from_logger(record.name)
                if record.levelno >= logging.ERROR:
                    tracker.indexer.add_error(
                        module=module,
                        error_type=record.levelname,
                        message=record.getMessage(),
                        location=location
                    )
                else:
                    tracker.indexer.add_warning(
                        module=module,
                        message=record.getMessage(),
                        location=location
                    )
            
            # Track the error (original behavior for errors only)
            if record.levelno >= logging.ERROR:
                tracker.track_error(
                    error_type=record.levelname,
                    error_msg=record.getMessage(),
                    location=location,
                    traceback_str=traceback_str,
                    severity=severity
                )


def setup_error_tracking():
    """Set up error tracking for the entire application"""
    # Initialize error tracker
    tracker = get_error_tracker()
    
    # SOTA 2026: Initialize warnings/errors indexer
    tracker.indexer = WarningsErrorsIndexer(tracker)
    print(f"📋 Warnings/Errors Index: {tracker.indexer.summary_file}")
    
    # Add error tracking handler to root logger
    root_logger = logging.getLogger()
    error_handler = ErrorTrackingHandler()
    error_handler.setLevel(logging.WARNING)
    root_logger.addHandler(error_handler)
    
    # ================================================================
    # 2025 SOTA: COMPREHENSIVE LOGGING - Capture ALL terminal output
    # ================================================================
    # Create a file handler that logs EVERYTHING (DEBUG and above)
    all_logs_file = tracker.logs_dir / f"all_logs_{tracker.session_id}.log"
    max_bytes = 10 * 1024 * 1024
    backup_count = 5
    file_handler = logging.handlers.RotatingFileHandler(
        all_logs_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    root_logger.addHandler(file_handler)
    
    # Also redirect stdout/stderr to capture print statements
    class TeeOutput:
        """Tee output to both original stream and log file"""
        def __init__(self, original, log_file, max_bytes: int, backup_count: int):
            self.original = original
            self.log_file = log_file
            self.max_bytes = max_bytes
            self.backup_count = backup_count

        def _rotate_if_needed(self):
            try:
                if not os.path.exists(self.log_file):
                    return
                size = os.path.getsize(self.log_file)
                if size < self.max_bytes:
                    return
                last = f"{self.log_file}.{self.backup_count}"
                if os.path.exists(last):
                    os.remove(last)
                for i in range(self.backup_count - 1, 0, -1):
                    src = f"{self.log_file}.{i}"
                    dst = f"{self.log_file}.{i + 1}"
                    if os.path.exists(src):
                        os.replace(src, dst)
                os.replace(self.log_file, f"{self.log_file}.1")
            except Exception:
                pass
             
        def write(self, text):
            self.original.write(text)
            if text.strip():  # Only log non-empty lines
                try:
                    self._rotate_if_needed()
                    with open(self.log_file, 'a') as f:
                        f.write(f"[STDOUT] {text}")
                except Exception:
                    pass
                    
        def flush(self):
            self.original.flush()
    
    # Capture stdout to log file
    stdout_log = tracker.logs_dir / f"stdout_{tracker.session_id}.log"
    sys.stdout = TeeOutput(sys.__stdout__, stdout_log, max_bytes=max_bytes, backup_count=backup_count)
     
    # Capture stderr to log file  
    stderr_log = tracker.logs_dir / f"stderr_{tracker.session_id}.log"
    sys.stderr = TeeOutput(sys.__stderr__, stderr_log, max_bytes=max_bytes, backup_count=backup_count)
    
    print(f"✅ Error tracking enabled - All errors will be logged to: {tracker.logs_dir}")
    print(f"📝 All logs: {all_logs_file}")
    print(f"📝 Stdout: {stdout_log}")
    print(f"📝 Stderr: {stderr_log}")
    
    return tracker


if __name__ == "__main__":
    # Test the error tracker
    tracker = setup_error_tracking()
    
    # Simulate some errors
    track_error("ImportError", "Module 'test' not found", "test.py:10", severity="ERROR")
    track_error("AttributeError", "'NoneType' object has no attribute 'test'", "main.py:50", severity="ERROR")
    track_error("ImportError", "Module 'test' not found", "test.py:10", severity="ERROR")  # Duplicate
    
    # Print summary
    tracker.print_summary()
    
    print("\n✅ Check the logs directory for detailed error reports!")
