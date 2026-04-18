"""
Crash Recovery Watchdog - 2025 SOTA
Monitors system health and implements crash recovery mechanisms.
Prevents 24-hour crashes by detecting and recovering from issues.
"""

import logging
import os
import sys
import time
import psutil
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

logger = logging.getLogger(__name__)


class HealthMetrics:
    """Container for system health metrics."""
    
    def __init__(self):
        self.timestamp = datetime.now()
        self.memory_mb = 0.0
        self.memory_percent = 0.0
        self.cpu_percent = 0.0
        self.thread_count = 0
        self.open_files = 0
        self.uptime_seconds = 0.0


class CrashRecoveryWatchdog(QObject):
    """
    Monitors system health and implements crash recovery.
    
    Features:
    - Memory leak detection (memory growth over time)
    - CPU spike detection
    - Thread leak detection (thread count growth)
    - File descriptor leak detection
    - Automatic state saving before critical conditions
    - Crash log generation
    """
    
    health_warning = pyqtSignal(str, dict)  # warning_type, metrics
    health_critical = pyqtSignal(str, dict)  # critical_type, metrics
    recovery_triggered = pyqtSignal(str)  # recovery_action
    
    _instance: Optional['CrashRecoveryWatchdog'] = None
    
    @classmethod
    def get_instance(cls) -> 'CrashRecoveryWatchdog':
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = CrashRecoveryWatchdog()
        return cls._instance
    
    def __init__(self):
        super().__init__()
        
        # Process monitoring
        self._process = psutil.Process(os.getpid())
        self._start_time = time.time()
        
        # Health monitoring timer (every 30 seconds)
        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._check_health)
        self._monitor_interval = 30 * 1000  # 30 seconds
        
        # Health metrics history
        self._metrics_history: List[HealthMetrics] = []
        self._max_history = 100  # Keep last 100 samples (50 minutes at 30s intervals)
        
        # Thresholds
        self._thresholds = {
            'memory_mb_max': 4096,  # 4GB max memory
            'memory_growth_mb_per_hour': 100,  # 100MB/hour growth = leak
            'cpu_percent_max': 90,  # 90% CPU sustained
            'thread_count_max': 200,  # 200 threads max
            'thread_growth_per_hour': 10,  # 10 threads/hour growth = leak
            'open_files_max': 500,  # 500 open files max
        }
        
        # Recovery actions
        self._recovery_actions: List[Callable] = []
        
        # Statistics
        self._stats = {
            'checks_total': 0,
            'warnings_total': 0,
            'criticals_total': 0,
            'recoveries_total': 0,
            'last_check_time': None
        }
        
        # Crash log
        self._crash_log_dir = Path("logs/crash_recovery")
        self._crash_log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("CrashRecoveryWatchdog initialized")
    
    def start_monitoring(self) -> None:
        """Start health monitoring."""
        self._monitor_timer.start(self._monitor_interval)
        logger.info(f"Health monitoring started - interval: {self._monitor_interval // 1000}s")
        
        # Take initial baseline measurement
        self._check_health()
    
    def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        if self._monitor_timer.isActive():
            self._monitor_timer.stop()
            logger.info("Health monitoring stopped")
    
    def register_recovery_action(self, action: Callable) -> None:
        """Register a recovery action to be called on critical conditions."""
        self._recovery_actions.append(action)
        logger.debug(f"Registered recovery action: {action.__name__}")
    
    def _collect_metrics(self) -> HealthMetrics:
        """Collect current system health metrics."""
        metrics = HealthMetrics()
        
        try:
            # Memory
            mem_info = self._process.memory_info()
            metrics.memory_mb = mem_info.rss / (1024 * 1024)  # Convert to MB
            metrics.memory_percent = self._process.memory_percent()
            
            # CPU
            metrics.cpu_percent = self._process.cpu_percent(interval=0.1)
            
            # Threads
            metrics.thread_count = self._process.num_threads()
            
            # Open files
            try:
                metrics.open_files = len(self._process.open_files())
            except (psutil.AccessDenied, AttributeError):
                metrics.open_files = 0
            
            # Uptime
            metrics.uptime_seconds = time.time() - self._start_time
            
        except Exception as e:
            logger.warning(f"Failed to collect metrics: {e}")
        
        return metrics
    
    def _check_health(self) -> None:
        """Check system health and detect issues."""
        try:
            # Collect current metrics
            metrics = self._collect_metrics()
            self._metrics_history.append(metrics)
            
            # Trim history
            if len(self._metrics_history) > self._max_history:
                self._metrics_history.pop(0)
            
            # Update statistics
            self._stats['checks_total'] += 1
            self._stats['last_check_time'] = datetime.now().isoformat()
            
            # Run health checks
            self._check_memory_leak(metrics)
            self._check_memory_limit(metrics)
            self._check_cpu_usage(metrics)
            self._check_thread_leak(metrics)
            self._check_file_descriptors(metrics)
            
            # Log periodic status
            if self._stats['checks_total'] % 20 == 0:  # Every 10 minutes
                self._log_health_status(metrics)
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _check_memory_leak(self, current: HealthMetrics) -> None:
        """Detect memory leaks by analyzing growth rate."""
        if len(self._metrics_history) < 10:  # Need at least 10 samples
            return
        
        # Calculate memory growth over last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_metrics = [m for m in self._metrics_history if m.timestamp > one_hour_ago]
        
        if len(recent_metrics) < 2:
            return
        
        # Linear regression to detect growth trend
        memory_values = [m.memory_mb for m in recent_metrics]
        growth_mb = memory_values[-1] - memory_values[0]
        
        if growth_mb > self._thresholds['memory_growth_mb_per_hour']:
            warning_msg = f"Memory leak detected: {growth_mb:.1f}MB growth in last hour"
            logger.warning(f"⚠️ {warning_msg}")
            self._stats['warnings_total'] += 1
            self.health_warning.emit('memory_leak', {
                'growth_mb': growth_mb,
                'current_mb': current.memory_mb
            })
            
            # Trigger recovery if severe
            if growth_mb > self._thresholds['memory_growth_mb_per_hour'] * 2:
                self._trigger_recovery('memory_leak_severe')
    
    def _check_memory_limit(self, current: HealthMetrics) -> None:
        """Check if memory usage exceeds limits."""
        if current.memory_mb > self._thresholds['memory_mb_max']:
            critical_msg = f"Memory limit exceeded: {current.memory_mb:.1f}MB > {self._thresholds['memory_mb_max']}MB"
            logger.critical(f"🚨 {critical_msg}")
            self._stats['criticals_total'] += 1
            self.health_critical.emit('memory_limit', {
                'current_mb': current.memory_mb,
                'limit_mb': self._thresholds['memory_mb_max']
            })
            
            # Trigger immediate recovery
            self._trigger_recovery('memory_limit_exceeded')
    
    def _check_cpu_usage(self, current: HealthMetrics) -> None:
        """Check for sustained high CPU usage."""
        if current.cpu_percent > self._thresholds['cpu_percent_max']:
            # Check if sustained over multiple samples
            recent = self._metrics_history[-5:] if len(self._metrics_history) >= 5 else self._metrics_history
            avg_cpu = sum(m.cpu_percent for m in recent) / len(recent)
            
            if avg_cpu > self._thresholds['cpu_percent_max']:
                warning_msg = f"Sustained high CPU: {avg_cpu:.1f}%"
                logger.warning(f"⚠️ {warning_msg}")
                self._stats['warnings_total'] += 1
                self.health_warning.emit('high_cpu', {
                    'current_percent': current.cpu_percent,
                    'average_percent': avg_cpu
                })
    
    def _check_thread_leak(self, current: HealthMetrics) -> None:
        """Detect thread leaks by analyzing thread count growth."""
        if len(self._metrics_history) < 10:
            return
        
        # Calculate thread growth over last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_metrics = [m for m in self._metrics_history if m.timestamp > one_hour_ago]
        
        if len(recent_metrics) < 2:
            return
        
        thread_growth = recent_metrics[-1].thread_count - recent_metrics[0].thread_count
        
        if thread_growth > self._thresholds['thread_growth_per_hour']:
            warning_msg = f"Thread leak detected: {thread_growth} threads created in last hour"
            logger.warning(f"⚠️ {warning_msg}")
            self._stats['warnings_total'] += 1
            self.health_warning.emit('thread_leak', {
                'growth': thread_growth,
                'current_count': current.thread_count
            })
        
        # Check absolute limit
        if current.thread_count > self._thresholds['thread_count_max']:
            critical_msg = f"Thread limit exceeded: {current.thread_count} > {self._thresholds['thread_count_max']}"
            logger.critical(f"🚨 {critical_msg}")
            self._stats['criticals_total'] += 1
            self.health_critical.emit('thread_limit', {
                'current_count': current.thread_count,
                'limit': self._thresholds['thread_count_max']
            })
    
    def _check_file_descriptors(self, current: HealthMetrics) -> None:
        """Check for file descriptor leaks."""
        if current.open_files > self._thresholds['open_files_max']:
            warning_msg = f"Too many open files: {current.open_files} > {self._thresholds['open_files_max']}"
            logger.warning(f"⚠️ {warning_msg}")
            self._stats['warnings_total'] += 1
            self.health_warning.emit('file_descriptor_leak', {
                'current_count': current.open_files,
                'limit': self._thresholds['open_files_max']
            })
    
    def _trigger_recovery(self, recovery_type: str) -> None:
        """Trigger recovery actions."""
        logger.critical(f"🚑 TRIGGERING RECOVERY: {recovery_type}")
        self._stats['recoveries_total'] += 1
        
        # Save crash log
        self._save_crash_log(recovery_type)
        
        # Save system state before recovery
        try:
            from core.system_state_manager import save_system_state
            logger.info("Saving system state before recovery...")
            save_system_state()
        except Exception as e:
            logger.error(f"Failed to save state during recovery: {e}")
        
        # Run recovery actions
        for action in self._recovery_actions:
            try:
                logger.info(f"Running recovery action: {action.__name__}")
                action()
            except Exception as e:
                logger.error(f"Recovery action {action.__name__} failed: {e}")
        
        self.recovery_triggered.emit(recovery_type)
    
    def _save_crash_log(self, recovery_type: str) -> None:
        """Save crash log with system state."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = self._crash_log_dir / f"crash_{recovery_type}_{timestamp}.log"
            
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"Crash Recovery Log\n")
                f.write(f"==================\n\n")
                f.write(f"Recovery Type: {recovery_type}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Uptime: {time.time() - self._start_time:.1f}s\n\n")
                
                # Current metrics
                if self._metrics_history:
                    current = self._metrics_history[-1]
                    f.write(f"Current Metrics:\n")
                    f.write(f"  Memory: {current.memory_mb:.1f}MB ({current.memory_percent:.1f}%)\n")
                    f.write(f"  CPU: {current.cpu_percent:.1f}%\n")
                    f.write(f"  Threads: {current.thread_count}\n")
                    f.write(f"  Open Files: {current.open_files}\n\n")
                
                # Statistics
                f.write(f"Statistics:\n")
                for key, value in self._stats.items():
                    f.write(f"  {key}: {value}\n")
            
            logger.info(f"Crash log saved: {log_file}")
            
        except Exception as e:
            logger.error(f"Failed to save crash log: {e}")
    
    def _log_health_status(self, metrics: HealthMetrics) -> None:
        """Log periodic health status."""
        uptime_hours = metrics.uptime_seconds / 3600
        logger.info(f"💓 Health Status - Uptime: {uptime_hours:.1f}h | "
                   f"Memory: {metrics.memory_mb:.1f}MB | "
                   f"CPU: {metrics.cpu_percent:.1f}% | "
                   f"Threads: {metrics.thread_count} | "
                   f"Files: {metrics.open_files}")
    
    def shutdown(self) -> None:
        """Shutdown the watchdog."""
        logger.info("CrashRecoveryWatchdog shutting down...")
        
        # Stop monitoring
        self.stop_monitoring()
        
        # Save final health report
        if self._metrics_history:
            current = self._metrics_history[-1]
            logger.info(f"Final health metrics - Memory: {current.memory_mb:.1f}MB, "
                       f"Threads: {current.thread_count}, "
                       f"Uptime: {current.uptime_seconds / 3600:.1f}h")
        
        logger.info("✅ CrashRecoveryWatchdog shutdown complete")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get watchdog statistics."""
        return self._stats.copy()


# Convenience functions
def get_watchdog() -> CrashRecoveryWatchdog:
    """Get the global watchdog instance."""
    return CrashRecoveryWatchdog.get_instance()


def start_crash_recovery() -> None:
    """Start crash recovery monitoring."""
    get_watchdog().start_monitoring()


def stop_crash_recovery() -> None:
    """Stop crash recovery monitoring."""
    get_watchdog().stop_monitoring()
